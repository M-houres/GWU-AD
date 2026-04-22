from datetime import datetime, timezone
from decimal import Decimal
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.client_source import DEFAULT_CLIENT_SOURCE, MINIPROGRAM_CLIENT_SOURCE, get_client_source
from app.config import get_settings
from app.constants import DEFAULT_BILLING_PACKAGES, PACKAGE_CONFIG
from app.deps import current_user, db_dep, get_redis
from app.exceptions import BizError
from app.money import cny_to_api, cny_to_fen, fen_to_cny, to_cny_decimal
from app.models import CreditTransaction, CreditType, Order, SystemConfig, User
from app.responses import ok
from app.schemas import APIResp, CreateOrderReq, MockPayReq, PayCallbackReq
from app.services.credit_service import change_credits
from app.services.payment_service import (
    create_payment_session,
    enabled_payment_providers,
    load_payment_config,
    normalize_payment_provider,
    parse_alipay_notify,
    parse_wechatpay_notify,
    query_remote_order_status,
    verify_payload_signature,
)
from app.services.partner_rebate_service import (
    attach_order_attribution_from_request,
)
from app.utils import make_order_no
from app.utils_qrcode import build_qrcode_data_url

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("app.api.billing")
ORDER_PAY_TIMEOUT_SECONDS = 300
SUPPORTED_PROVIDERS = {"wechat", "alipay", "mock"}
SUPPORTED_SCENES = {"web", "miniprogram"}
MINIPROGRAM_SCENE = "miniprogram"
CUSTOM_RECHARGE_MIN_CNY = Decimal("1.00")
CUSTOM_RECHARGE_MAX_CNY = Decimal("50000.00")
PACKAGE_NAME_ALIASES = {
    "年费包": "大额包",
}


def _normalize_payment_scene(scene: str | None, *, fallback_source: str = DEFAULT_CLIENT_SOURCE) -> str:
    raw = str(scene or "").strip().lower().replace("-", "_")
    if raw in {"miniapp", "miniprogram", "mini_program", "wxapp", "wechat_miniprogram", "wechat_mini_program"}:
        return MINIPROGRAM_SCENE
    if raw in {"web", "site", "h5"}:
        return "web"
    return MINIPROGRAM_SCENE if fallback_source == MINIPROGRAM_CLIENT_SOURCE else "web"


def _normalize_package_name(name: str) -> str:
    raw = str(name or "").strip()
    return PACKAGE_NAME_ALIASES.get(raw, raw)


def _load_available_packages(db: Session) -> list[dict]:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == "billing")
        .first()
    )
    cfg = row.config_value if row and isinstance(row.config_value, dict) else {}
    raw_packages = cfg.get("packages")
    normalized: list[dict] = []
    seen_names: set[str] = set()

    if isinstance(raw_packages, list):
        for item in raw_packages:
            if not isinstance(item, dict):
                continue
            name = _normalize_package_name(item.get("name", ""))
            if not name or name in seen_names:
                continue
            try:
                price = round(float(item.get("price", 0)), 2)
                credits = int(item.get("credits", cny_to_fen(Decimal(str(price or 0)))))
            except Exception:
                continue
            enabled = bool(item.get("enabled", True))
            if price <= 0 or credits <= 0 or (not enabled):
                continue
            seen_names.add(name)
            normalized.append(
                {
                    "name": name,
                    "price": price,
                    "credits": credits,
                    "description": str(item.get("description", "")).strip(),
                    "badge": str(item.get("badge", "")).strip(),
                }
            )

    if normalized:
        return normalized

    return [
        {
            "name": _normalize_package_name(item["name"]),
            "price": round(float(item["price"]), 2),
            "credits": int(item["credits"]),
            "description": str(item.get("description", "")).strip(),
            "badge": str(item.get("badge", "")).strip(),
        }
        for item in DEFAULT_BILLING_PACKAGES
        if bool(item.get("enabled", True))
    ]


def _find_package(db: Session, package_name: str) -> dict | None:
    normalized_name = _normalize_package_name(package_name)
    by_name = {item["name"]: item for item in _load_available_packages(db)}
    package = by_name.get(normalized_name)
    if package:
        return package
    # backward compatibility fallback for historical constant-only orders
    legacy = PACKAGE_CONFIG.get(normalized_name) or PACKAGE_CONFIG.get(package_name)
    if legacy:
        return {
            "name": normalized_name,
            "price": round(float(legacy["price"]), 2),
            "credits": int(legacy["credits"]),
            "description": "",
            "badge": "",
        }
    return None


def _order_amount_fen(order: Order) -> int:
    return int(order.credits or 0)


def _order_amount_cny_api(order: Order) -> float:
    return cny_to_api(order.amount_cny)


def _resolve_recharge_amount(req: CreateOrderReq, db: Session) -> tuple[Decimal, str, int]:
    if req.amount_cny is not None:
        raise BizError(code=4221, message="当前仅支持按通用点数套餐充值", http_status=422)

    package_name = _normalize_package_name(req.package_name or "")
    if not package_name:
        raise BizError(code=4201, message="请选择通用点数套餐", http_status=422)
    pkg = _find_package(db, package_name)
    if pkg is None:
        raise BizError(code=4201, message="套餐不存在")
    return to_cny_decimal(pkg["price"]), package_name, int(pkg["credits"])


def _settle_package_order(
    db: Session,
    *,
    user: User,
    package_name: str,
    order_no: str,
    provider: str,
    amount_cny: Decimal | float | str | None = None,
    recharge_credits: int | None = None,
    source: str | None = None,
) -> tuple[Order, bool]:
    normalized_package_name = _normalize_package_name(package_name or "")
    if amount_cny is None:
        pkg = _find_package(db, normalized_package_name)
        if pkg is None:
            raise BizError(code=4201, message="套餐不存在")
        paid_amount = to_cny_decimal(pkg["price"])
        package_credits = int(pkg["credits"])
        display_name = normalized_package_name or str(pkg["name"])
    else:
        paid_amount = to_cny_decimal(amount_cny)
        if paid_amount < CUSTOM_RECHARGE_MIN_CNY or paid_amount > CUSTOM_RECHARGE_MAX_CNY:
            raise BizError(
                code=4221,
                message=f"自定义充值金额需在 {cny_to_api(CUSTOM_RECHARGE_MIN_CNY):.2f}~{cny_to_api(CUSTOM_RECHARGE_MAX_CNY):.2f} 元之间",
                http_status=422,
            )
        package_credits = int(recharge_credits) if recharge_credits is not None else cny_to_fen(paid_amount)
        display_name = normalized_package_name or f"自定义充值 ¥{cny_to_api(paid_amount):.2f}"

    locked_user = db.query(User).filter(User.id == user.id).with_for_update().first()
    if locked_user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)

    order = db.query(Order).filter(Order.order_no == order_no).with_for_update().first()
    if order and order.user_id != user.id:
        raise BizError(code=4208, message="订单归属用户不匹配")
    if order and order.status == "paid":
        return order, True

    recharge_fen = package_credits if package_credits > 0 else cny_to_fen(paid_amount)
    order_source = source or getattr(user, "source", "") or DEFAULT_CLIENT_SOURCE
    if order is None:
        has_paid = (
            db.query(Order)
            .filter(Order.user_id == user.id, Order.status == "paid")
            .count()
            > 0
        )
        order = Order(
            order_no=order_no,
            user_id=user.id,
            amount_cny=paid_amount,
            credits=recharge_fen,
            source=order_source,
            status="paid",
            provider=provider,
            is_first_pay=not has_paid,
        )
        db.add(order)
        db.flush()
    else:
        paid_count = (
            db.query(Order)
            .filter(
                Order.user_id == user.id,
                Order.status == "paid",
                Order.id != order.id,
            )
            .count()
        )
        order.amount_cny = paid_amount
        order.credits = recharge_fen
        if not order.source:
            order.source = order_source
        order.status = "paid"
        order.provider = provider
        order.is_first_pay = paid_count == 0
        db.flush()

    existed_tx = (
        db.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user.id,
            CreditTransaction.tx_type == CreditType.PACKAGE_PAY,
            CreditTransaction.related_id == order_no,
        )
        .first()
    )
    if existed_tx:
        return order, True

    change_credits(
        db,
        locked_user,
        tx_type=CreditType.PACKAGE_PAY,
        delta=recharge_fen,
        reason=f"通用点数充值到账:{display_name}",
        related_id=order_no,
        source=order.source or order_source,
    )
    return order, False


def _build_qrcode_data(pay_url: str) -> str:
    return build_qrcode_data_url(pay_url)


def _pay_pending_order(db: Session, order: Order) -> tuple[Order, bool]:
    if order.status == "paid":
        return order, True
    if order.status == "refunded":
        raise BizError(code=4209, message="璁㈠崟宸查€€娆撅紝涓嶅彲閲嶅鏀粯")
    if order.status == "closed":
        raise BizError(code=4210, message="订单已关闭，请重新下单")

    existing_tx = (
        db.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == order.user_id,
            CreditTransaction.tx_type == CreditType.PACKAGE_PAY,
            CreditTransaction.related_id == order.order_no,
        )
        .first()
    )
    if existing_tx:
        order.status = "paid"
        db.flush()
        return order, True

    user = db.query(User).filter(User.id == order.user_id).with_for_update().first()
    if user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)
    has_paid = (
        db.query(Order)
        .filter(Order.user_id == order.user_id, Order.status == "paid", Order.id != order.id)
        .count()
        > 0
    )
    order.status = "paid"
    order.is_first_pay = not has_paid
    change_credits(
        db,
        user,
        tx_type=CreditType.PACKAGE_PAY,
        delta=order.credits,
        reason=f"通用点数充值到账:{order.order_no}",
        related_id=order.order_no,
        source=order.source or getattr(user, "source", "") or DEFAULT_CLIENT_SOURCE,
    )
    db.flush()
    return order, False


def _calc_remain_seconds(order: Order) -> int:
    delta = datetime.utcnow() - order.created_at
    elapsed = int(delta.total_seconds())
    return max(0, ORDER_PAY_TIMEOUT_SECONDS - elapsed)


def _payment_replay_key(provider: str, nonce: str) -> str:
    normalized_provider = normalize_payment_provider(provider)
    return f"payment:callback:nonce:{normalized_provider}:{str(nonce or '').strip()}"


def _consume_callback_nonce(redis_conn, *, provider: str, nonce: str) -> None:
    normalized_nonce = str(nonce or "").strip()
    if not normalized_nonce:
        raise BizError(code=4205, message="支付回调缺少 nonce")
    key = _payment_replay_key(provider, normalized_nonce)
    ttl_seconds = max(int(settings.payment_callback_ttl_seconds or 900), 60)
    if hasattr(redis_conn, "set"):
        accepted = redis_conn.set(key, "1", ex=ttl_seconds, nx=True)
    else:
        existing = redis_conn.get(key)
        if existing:
            accepted = False
        else:
            redis_conn.setex(key, ttl_seconds, "1")
            accepted = True
    if not accepted:
        raise BizError(code=4205, message="支付回调重复，请勿重放")


def _find_reusable_open_order(
    db: Session,
    *,
    user_id: int,
    provider: str,
    amount_cny: Decimal,
    recharge_fen: int,
) -> Order | None:
    rows = (
        db.query(Order)
        .filter(
            Order.user_id == user_id,
            Order.status == "created",
            Order.provider == provider,
            Order.amount_cny == amount_cny,
            Order.credits == recharge_fen,
        )
        .order_by(Order.created_at.desc())
        .with_for_update()
        .all()
    )
    for row in rows:
        if _calc_remain_seconds(row) > 0:
            return row
    return None


def _frontend_base_url(request: Request | None = None) -> str:
    if request is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
        if forwarded_host:
            scheme = forwarded_proto or request.url.scheme or "https"
            return f"{scheme}://{forwarded_host}".rstrip("/")
        return str(request.base_url).rstrip("/")
    raw = str(settings.frontend_base_url or "").strip()
    if raw:
        return raw.rstrip("/")
    return "http://localhost"


def _default_mock_pay_url(order_no: str, request: Request | None = None) -> str:
    return f"{_frontend_base_url(request)}/app/buy?order_no={order_no}&provider=mock"

def _assert_paid_amount_matches(order: Order, amount_cny: Decimal | float | str | None) -> None:
    if amount_cny is None:
        return
    actual = to_cny_decimal(amount_cny)
    expected = to_cny_decimal(order.amount_cny)
    if actual != expected:
        raise BizError(code=4207, message="鏀粯閲戦涓庤鍗曢噾棰濅笉鍖归厤")


def _settle_existing_order(
    db: Session,
    *,
    order_no: str,
    provider: str,
    amount_cny: Decimal | float | str | None = None,
) -> tuple[Order, bool]:
    order = db.query(Order).filter(Order.order_no == order_no).with_for_update().first()
    if order is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    _assert_paid_amount_matches(order, amount_cny)
    order.provider = provider
    settled_order, idempotent = _pay_pending_order(db, order)
    return settled_order, idempotent


def _wechat_ack(success: bool, message: str) -> JSONResponse:
    if success:
        return JSONResponse(status_code=200, content={"code": "SUCCESS", "message": message})
    return JSONResponse(status_code=400, content={"code": "FAIL", "message": message})


@router.get("/packages", response_model=APIResp)
def packages(
    request: Request,
    scene: str | None = None,
    db: Session = Depends(db_dep),
) -> APIResp:
    client_source = get_client_source(request)
    normalized_scene = _normalize_payment_scene(scene, fallback_source=client_source)
    payment_cfg = load_payment_config(db)
    supported_providers = enabled_payment_providers(db, scene=normalized_scene)
    payment_test_mode = bool(payment_cfg.get("test_mode", settings.payment_test_mode))
    if normalized_scene == MINIPROGRAM_SCENE and supported_providers == ["mock"]:
        payment_test_mode = True
    payment_mode = payment_cfg.get("provider", "wechatpay_v3")
    items = [
        {
            **item,
            "amount_cny": round(float(item["price"]), 2),
        }
        for item in _load_available_packages(db)
    ]
    if normalized_scene == MINIPROGRAM_SCENE:
        if supported_providers == ["wechat"]:
            message = "小程序当前为微信支付模式"
        elif supported_providers == ["mock"]:
            message = "小程序当前使用测试支付模式"
        else:
            message = "小程序支付通道未就绪"
    else:
        message = "当前为联调支付模式" if payment_test_mode else "当前为正式支付模式"
        if not supported_providers:
            message = "支付通道未就绪"
    return ok(
        data={
            "items": items,
            "payment_test_mode": payment_test_mode,
            "message": message,
            "supported_providers": supported_providers,
            "payment_provider_mode": payment_mode,
            "scene": normalized_scene,
            "custom_amount_enabled": False,
        }
    )


@router.post("/create-order", response_model=APIResp)
def create_order(
    req: CreateOrderReq,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    amount_cny, package_name, recharge_credits = _resolve_recharge_amount(req, db)

    requested_provider = req.provider.strip().lower()
    provider = requested_provider
    scene = str(req.scene or "web").strip().lower() or "web"
    logger.info(
        "billing_create_order_checkpoint_in",
        extra={
            "user_id": user.id,
            "provider_requested": requested_provider,
            "scene_requested": scene,
            "package_name": package_name,
            "amount_cny": cny_to_api(amount_cny),
        },
    )
    if scene not in SUPPORTED_SCENES:
        raise BizError(code=4211, message="支付场景不支持")

    enabled = set(enabled_payment_providers(db, scene=scene))
    payment_cfg = load_payment_config(db)
    payment_test_mode = bool(payment_cfg.get("test_mode", settings.payment_test_mode))

    if provider not in SUPPORTED_PROVIDERS:
        raise BizError(code=4211, message="支付方式不支持")
    if provider not in enabled:
        if scene == MINIPROGRAM_SCENE and provider == "wechat" and "mock" in enabled and (not settings.is_prod):
            provider = "mock"
            payment_test_mode = True
        elif scene == MINIPROGRAM_SCENE and provider == "wechat":
            raise BizError(code=4214, message="小程序微信支付未就绪，请检查微信支付配置")
        else:
            raise BizError(code=4211, message="支付方式不支持")
    if provider == "mock" and settings.is_prod:
        raise BizError(code=4213, message="生产环境不允许使用测试支付")

    if scene == MINIPROGRAM_SCENE and provider == "wechat" and not str(user.wechat_openid_mp or "").strip():
        raise BizError(code=4216, message="小程序支付缺少openid，请重新登录")

    locked_user = db.query(User).filter(User.id == user.id).with_for_update().first()
    if locked_user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)

    client_source = get_client_source(request)
    recharge_fen = int(recharge_credits)
    reused_open_order = False
    order = _find_reusable_open_order(
        db,
        user_id=user.id,
        provider=provider,
        amount_cny=amount_cny,
        recharge_fen=recharge_fen,
    )
    if order is None:
        order_no = make_order_no()
        order = Order(
            order_no=order_no,
            user_id=user.id,
            amount_cny=amount_cny,
            credits=recharge_fen,
            source=client_source,
            status="created",
            provider=provider,
            is_first_pay=False,
        )
        db.add(order)
        db.flush()
    else:
        reused_open_order = True
        order_no = order.order_no

    attach_order_attribution_from_request(
        db,
        request=request,
        user_id=user.id,
        order=order,
        package_name=package_name,
        explicit_channel_code=req.channel_code,
        explicit_channel_token=req.channel_token,
    )

    pay_url = _default_mock_pay_url(order_no, request)
    payment_params: dict | None = None
    if provider != "mock":
        try:
            session = create_payment_session(
                db,
                order=order,
                package_name=package_name,
                scene=scene,
                wechat_openid=user.wechat_openid_mp,
            )
            pay_url = str(session.get("pay_url", "")).strip()
            if isinstance(session.get("payment_params"), dict):
                payment_params = session["payment_params"]
            if scene != MINIPROGRAM_SCENE and not pay_url:
                raise BizError(code=4214, message="支付通道未返回支付链接")
        except BizError as exc:
            if settings.is_prod:
                raise
            if exc.code not in {4211, 4214}:
                raise
            logger.warning(
                "billing_create_order_dev_fallback_to_mock",
                extra={
                    "order_no": order_no,
                    "user_id": user.id,
                    "provider": provider,
                    "scene": scene,
                    "reason_code": exc.code,
                },
            )
            provider = "mock"
            order.provider = "mock"
            pay_url = _default_mock_pay_url(order_no, request)
            payment_params = None

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "billing_order_created",
        extra={
            "order_no": order_no,
            "user_id": user.id,
            "provider": provider,
            "scene": scene,
            "amount_cny": cny_to_api(order.amount_cny),
            "recharge_fen": _order_amount_fen(order),
            "reused_open_order": reused_open_order,
        },
    )
    return ok(
        data={
            "order_no": order_no,
            "status": order.status,
            "provider": provider,
            "scene": scene,
            "provider_requested": requested_provider,
            "provider_fallback": provider != requested_provider,
            "amount_cny": cny_to_api(order.amount_cny),
            "recharge_fen": _order_amount_fen(order),
            "recharge_cny": _order_amount_cny_api(order),
            "package_name": package_name,
            "credits": order.credits,
            "expire_seconds": ORDER_PAY_TIMEOUT_SECONDS,
            "qrcode_data_url": _build_qrcode_data(pay_url) if pay_url else "",
            "payment_params": payment_params,
            "payment_test_mode": payment_test_mode,
        }
    )


@router.get("/order-status/{order_no}", response_model=APIResp)
def order_status(order_no: str, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    order = db.query(Order).filter(Order.order_no == order_no, Order.user_id == user.id).with_for_update().first()
    if order is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    logger.info(
        "billing_order_status_checkpoint_in",
        extra={
            "order_no": order.order_no,
            "user_id": user.id,
            "status": order.status,
            "provider": order.provider,
        },
    )
    if order.status == "created":
        remain = _calc_remain_seconds(order)
        if remain <= 0:
            order.status = "closed"
            db.commit()
            logger.info(
                "billing_order_status_checkpoint_timeout_closed",
                extra={"order_no": order.order_no, "user_id": user.id},
            )
            return ok(
                data={
                    "order_no": order.order_no,
                    "status": "closed",
                    "remain_seconds": 0,
                    "provider": order.provider,
                    "amount_cny": _order_amount_cny_api(order),
                    "recharge_fen": _order_amount_fen(order),
                }
            )

        if normalize_payment_provider(order.provider) in {"wechatpay_v3", "alipay"}:
            remote = query_remote_order_status(db, order=order)
            remote_status = str(remote.get("status", "created")).lower()
            logger.info(
                "billing_order_status_checkpoint_remote",
                extra={
                    "order_no": order.order_no,
                    "user_id": user.id,
                    "provider": order.provider,
                    "remote_status": remote_status,
                },
            )
            if remote_status == "paid":
                try:
                    settled_order, idempotent = _settle_existing_order(
                        db,
                        order_no=order.order_no,
                        provider=order.provider,
                        amount_cny=remote.get("amount_cny"),
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                logger.info(
                    "billing_order_status_checkpoint_remote_paid",
                    extra={
                        "order_no": settled_order.order_no,
                        "user_id": user.id,
                        "idempotent": idempotent,
                    },
                )
                return ok(
                    data={
                        "order_no": settled_order.order_no,
                        "status": settled_order.status,
                        "remain_seconds": 0,
                        "provider": settled_order.provider,
                        "amount_cny": _order_amount_cny_api(settled_order),
                        "recharge_fen": _order_amount_fen(settled_order),
                    }
                )
            if remote_status == "closed":
                order.status = "closed"
                db.commit()
                logger.info(
                    "billing_order_status_checkpoint_remote_closed",
                    extra={"order_no": order.order_no, "user_id": user.id},
                )
                return ok(
                    data={
                        "order_no": order.order_no,
                        "status": "closed",
                        "remain_seconds": 0,
                        "provider": order.provider,
                        "amount_cny": _order_amount_cny_api(order),
                        "recharge_fen": _order_amount_fen(order),
                    }
                )

        return ok(
            data={
                "order_no": order.order_no,
                "status": order.status,
                "remain_seconds": remain,
                "provider": order.provider,
                "amount_cny": _order_amount_cny_api(order),
                "recharge_fen": _order_amount_fen(order),
            }
        )
    return ok(
        data={
            "order_no": order.order_no,
            "status": order.status,
            "remain_seconds": 0,
            "provider": order.provider,
            "amount_cny": _order_amount_cny_api(order),
            "recharge_fen": _order_amount_fen(order),
        }
    )


@router.post("/order-pay/{order_no}", response_model=APIResp)
def order_pay(order_no: str, user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    order = db.query(Order).filter(Order.order_no == order_no, Order.user_id == user.id).with_for_update().first()
    if order is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    logger.info(
        "billing_order_pay_checkpoint_in",
        extra={
            "order_no": order_no,
            "user_id": user.id,
            "status": order.status,
            "provider": order.provider,
        },
    )
    payment_cfg = load_payment_config(db)
    payment_test_mode = bool(payment_cfg.get("test_mode", settings.payment_test_mode))
    if order.status == "created" and _calc_remain_seconds(order) <= 0:
        order.status = "closed"
        db.commit()
        raise BizError(code=4212, message="订单已超时，请重新下单")

    if normalize_payment_provider(order.provider) == "mock" and settings.is_prod:
        raise BizError(code=4213, message="生产环境不允许使用测试支付")

    if normalize_payment_provider(order.provider) != "mock" and not payment_test_mode:
        remote = query_remote_order_status(db, order=order)
        remote_status = str(remote.get("status", "")).lower()
        logger.info(
            "billing_order_pay_checkpoint_remote",
            extra={
                "order_no": order.order_no,
                "user_id": user.id,
                "provider": order.provider,
                "remote_status": remote_status,
            },
        )
        if remote_status != "paid":
            raise BizError(code=4215, message="请在微信或支付宝完成支付后再刷新订单状态")
        try:
            settled_order, idempotent = _settle_existing_order(
                db,
                order_no=order.order_no,
                provider=order.provider,
                amount_cny=remote.get("amount_cny"),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        logger.info(
            "billing_order_pay_checkpoint_remote_paid",
            extra={
                "order_no": settled_order.order_no,
                "user_id": user.id,
                "idempotent": idempotent,
            },
        )
        return ok(
            data={
                "order_no": settled_order.order_no,
                "status": settled_order.status,
                "idempotent": idempotent,
                "recharge_fen": _order_amount_fen(settled_order),
                "recharge_cny": _order_amount_cny_api(settled_order),
                "credits": settled_order.credits,
            }
        )

    try:
        settled_order, idempotent = _pay_pending_order(db, order)
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info(
        "billing_order_paid",
        extra={
            "order_no": settled_order.order_no,
            "user_id": user.id,
            "provider": settled_order.provider,
            "idempotent": idempotent,
        },
    )
    return ok(
        data={
            "order_no": settled_order.order_no,
            "status": settled_order.status,
            "idempotent": idempotent,
            "recharge_fen": _order_amount_fen(settled_order),
            "recharge_cny": _order_amount_cny_api(settled_order),
            "credits": settled_order.credits,
        }
    )


@router.post("/mock-pay", response_model=APIResp)
def mock_pay(
    req: MockPayReq,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    payment_cfg = load_payment_config(db)
    if settings.is_prod:
        raise BizError(code=4213, message="生产环境不允许使用测试支付")
    if not bool(payment_cfg.get("test_mode", settings.payment_test_mode)):
        raise BizError(code=4213, message="当前环境未开启测试支付")
    order_no = make_order_no()
    amount_cny, package_name, recharge_credits = _resolve_recharge_amount(
        CreateOrderReq(package_name=req.package_name, amount_cny=req.amount_cny),
        db,
    )
    try:
        order, idempotent = _settle_package_order(
            db,
            user=user,
            package_name=package_name,
            order_no=order_no,
            provider="mock",
            amount_cny=amount_cny,
            recharge_credits=recharge_credits,
            source=get_client_source(request),
        )
        attach_order_attribution_from_request(
            db,
            request=request,
            user_id=user.id,
            order=order,
            package_name=package_name,
            explicit_channel_code=None,
            explicit_channel_token=None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info(
        "billing_mock_pay_paid",
        extra={"order_no": order_no, "user_id": user.id, "idempotent": idempotent},
    )
    return ok(
        data={
            "order_no": order_no,
            "status": "paid",
            "idempotent": idempotent,
            "recharge_fen": _order_amount_fen(order),
            "recharge_cny": _order_amount_cny_api(order),
            "credits": order.credits,
        }
    )


@router.post("/callback", response_model=APIResp)
def pay_callback(
    req: PayCallbackReq,
    request: Request,
    db: Session = Depends(db_dep),
    redis_conn=Depends(get_redis),
) -> APIResp:
    logger.info(
        "billing_callback_checkpoint_in",
        extra={
            "order_no": req.order_no,
            "user_id": req.user_id,
            "provider": req.provider,
            "status": req.status,
        },
    )
    payload = req.model_dump(exclude={"sign"})
    if not verify_payload_signature(payload, req.sign, db=db):
        raise BizError(code=4204, message="鏀粯鍥炶皟楠岀澶辫触")

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if abs(now_ts - req.paid_at) > settings.payment_callback_ttl_seconds:
        raise BizError(code=4205, message="支付回调已过期")
    if req.status != "paid":
        raise BizError(code=4206, message="仅支持 paid 状态回调")
    _consume_callback_nonce(redis_conn, provider=req.provider, nonce=req.nonce)

    order = db.query(Order).filter(Order.order_no == req.order_no).with_for_update().first()
    if order is None:
        raise BizError(code=4044, message="订单不存在", http_status=404)
    if order.user_id != req.user_id:
        raise BizError(code=4208, message="订单归属用户不匹配")

    try:
        order, idempotent = _settle_existing_order(
            db,
            order_no=req.order_no,
            provider=req.provider,
            amount_cny=req.amount_cny,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info(
        "billing_callback_paid",
        extra={
            "order_no": order.order_no,
            "user_id": order.user_id,
            "provider": req.provider,
            "idempotent": idempotent,
        },
    )

    return ok(
        data={
            "order_no": order.order_no,
            "status": order.status,
            "recharge_fen": _order_amount_fen(order),
            "recharge_cny": _order_amount_cny_api(order),
            "credits": order.credits,
            "idempotent": idempotent,
        }
    )


@router.post("/notify/wechatpay")
async def wechatpay_notify(request: Request, db: Session = Depends(db_dep), redis_conn=Depends(get_redis)) -> JSONResponse:
    try:
        body = await request.body()
        notify_nonce = str(request.headers.get("Wechatpay-Nonce") or request.headers.get("wechatpay-nonce") or "").strip()
        result = parse_wechatpay_notify(db, body=body, headers=request.headers)
        logger.info(
            "billing_wechatpay_notify_checkpoint_in",
            extra={"order_no": result.get("order_no"), "status": result.get("status")},
        )
        _consume_callback_nonce(redis_conn, provider="wechat", nonce=notify_nonce)
        if result["status"] == "paid":
            try:
                order, idempotent = _settle_existing_order(
                    db,
                    order_no=result["order_no"],
                    provider="wechat",
                    amount_cny=result.get("amount_cny"),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            logger.info(
                "billing_wechatpay_notify_checkpoint_paid",
                extra={"order_no": order.order_no, "user_id": order.user_id, "idempotent": idempotent},
            )
        elif result["status"] == "closed":
            order = db.query(Order).filter(Order.order_no == result["order_no"]).with_for_update().first()
            if order and order.status == "created":
                order.status = "closed"
                db.commit()
            logger.info(
                "billing_wechatpay_notify_checkpoint_closed",
                extra={"order_no": result.get("order_no")},
            )
        return _wechat_ack(True, "鎴愬姛")
    except BizError as exc:
        logger.warning("billing_wechatpay_notify_failed", extra={"detail": exc.message})
        return _wechat_ack(False, exc.message)
    except Exception as exc:
        logger.exception("billing_wechatpay_notify_exception")
        return _wechat_ack(False, str(exc)[:120] or "鍥炶皟澶勭悊澶辫触")


@router.post("/notify/alipay")
async def alipay_notify(request: Request, db: Session = Depends(db_dep), redis_conn=Depends(get_redis)) -> PlainTextResponse:
    try:
        form = await request.form()
        notify_nonce = str(form.get("notify_id") or form.get("trade_no") or form.get("out_trade_no") or "").strip()
        result = parse_alipay_notify(form, db)
        logger.info(
            "billing_alipay_notify_checkpoint_in",
            extra={"order_no": result.get("order_no"), "status": result.get("status")},
        )
        _consume_callback_nonce(redis_conn, provider="alipay", nonce=notify_nonce)
        if result["status"] == "paid":
            try:
                order, idempotent = _settle_existing_order(
                    db,
                    order_no=result["order_no"],
                    provider="alipay",
                    amount_cny=result.get("amount_cny"),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            logger.info(
                "billing_alipay_notify_checkpoint_paid",
                extra={"order_no": order.order_no, "user_id": order.user_id, "idempotent": idempotent},
            )
        elif result["status"] == "closed":
            order = db.query(Order).filter(Order.order_no == result["order_no"]).with_for_update().first()
            if order and order.status == "created":
                order.status = "closed"
                db.commit()
            logger.info(
                "billing_alipay_notify_checkpoint_closed",
                extra={"order_no": result.get("order_no")},
            )
        return PlainTextResponse("success")
    except Exception as exc:
        logger.warning("billing_alipay_notify_failed", extra={"detail": str(exc)[:160]})
        return PlainTextResponse("failure", status_code=400)


