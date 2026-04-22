from __future__ import annotations

from datetime import datetime
import re
import secrets

from fastapi import Request
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.exceptions import BizError
from app.models import (
    Order,
    PartnerChannel,
    PartnerLedgerEntryType,
    PartnerLedgerStatus,
    PartnerMonthlyStatement,
    PartnerOrderAttribution,
    PartnerPolicy,
    PartnerRebateLedger,
    PartnerStatementStatus,
    PartnerUserBinding,
    PartnerWithdrawRequest,
    PartnerWithdrawStatus,
)
from app.money import cny_to_fen

settings = get_settings()

_CHANNEL_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,31}$")
_STATEMENT_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _normalize_channel_code(value: str | None) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9_-]", "", raw)[:32]


def _normalize_statement_month(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.utcnow().strftime("%Y-%m")
    if not _STATEMENT_MONTH_RE.match(raw):
        raise BizError(code=4460, message="结算月份格式错误，需为 YYYY-MM")
    year = int(raw[:4])
    month = int(raw[5:7])
    if year < 2000 or year > 2099 or month < 1 or month > 12:
        raise BizError(code=4460, message="结算月份不合法")
    return raw


def _statement_month_now() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _gen_channel_code(db: Session) -> str:
    for _ in range(20):
        candidate = f"CH{secrets.token_hex(4).upper()}"
        exists = db.query(PartnerChannel.id).filter(PartnerChannel.channel_code == candidate).first()
        if not exists:
            return candidate
    raise BizError(code=4461, message="渠道编码生成失败，请重试")


def _gen_unique_token(db: Session, *, column_name: str) -> str:
    for _ in range(24):
        candidate = secrets.token_urlsafe(24)
        query = db.query(PartnerChannel.id)
        if column_name == "order_token":
            exists = query.filter(PartnerChannel.order_token == candidate).first()
        else:
            exists = query.filter(PartnerChannel.portal_token == candidate).first()
        if not exists:
            return candidate
    raise BizError(code=4462, message="渠道令牌生成失败，请重试")


def _normalize_rebate_rate_bp(value: int | str | None) -> int:
    try:
        rate = int(value)
    except Exception as exc:
        raise BizError(code=4463, message="返佣比例必须是整数（基点）") from exc
    if rate < 0 or rate > 10000:
        raise BizError(code=4463, message="返佣比例超出范围，需在 0~10000 基点之间")
    return rate


def build_channel_links(channel: PartnerChannel) -> dict[str, str]:
    frontend_base = str(settings.frontend_base_url or "").strip().rstrip("/") or "http://127.0.0.1:5173"
    return {
        "order_link": f"{frontend_base}/app/detect?ch={channel.channel_code}&ck={channel.order_token}",
        "portal_link": f"{frontend_base}/app/partner?ch={channel.channel_code}&pk={channel.portal_token}",
    }


def create_partner_channel(
    db: Session,
    *,
    name: str,
    contact_name: str = "",
    contact_phone: str = "",
    channel_code: str | None = None,
    rebate_rate_bp: int = 1500,
) -> PartnerChannel:
    channel_name = str(name or "").strip()
    if not channel_name:
        raise BizError(code=4464, message="渠道名称不能为空")

    normalized_code = _normalize_channel_code(channel_code)
    if normalized_code:
        if not _CHANNEL_CODE_RE.match(normalized_code):
            raise BizError(code=4465, message="渠道编码格式不合法")
        exists = db.query(PartnerChannel.id).filter(PartnerChannel.channel_code == normalized_code).first()
        if exists:
            raise BizError(code=4466, message="渠道编码已存在")
    else:
        normalized_code = _gen_channel_code(db)

    normalized_rate = _normalize_rebate_rate_bp(rebate_rate_bp)
    channel = PartnerChannel(
        channel_code=normalized_code,
        name=channel_name[:120],
        contact_name=str(contact_name or "").strip()[:64],
        contact_phone=str(contact_phone or "").strip()[:64],
        status="active",
        order_token=_gen_unique_token(db, column_name="order_token"),
        portal_token=_gen_unique_token(db, column_name="portal_token"),
        default_rebate_rate_bp=normalized_rate,
    )
    db.add(channel)
    db.flush()
    db.add(
        PartnerPolicy(
            channel_id=channel.id,
            package_name=None,
            rebate_rate_bp=normalized_rate,
            is_active=True,
        )
    )
    db.flush()
    return channel


def update_partner_channel(
    db: Session,
    *,
    channel: PartnerChannel,
    name: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    status: str | None = None,
    rebate_rate_bp: int | None = None,
) -> PartnerChannel:
    if name is not None:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise BizError(code=4464, message="渠道名称不能为空")
        channel.name = normalized_name[:120]
    if contact_name is not None:
        channel.contact_name = str(contact_name or "").strip()[:64]
    if contact_phone is not None:
        channel.contact_phone = str(contact_phone or "").strip()[:64]
    if status is not None:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"active", "disabled"}:
            raise BizError(code=4467, message="渠道状态不合法")
        channel.status = normalized_status
    if rebate_rate_bp is not None:
        channel.default_rebate_rate_bp = _normalize_rebate_rate_bp(rebate_rate_bp)
    db.flush()
    return channel


def upsert_partner_policy(
    db: Session,
    *,
    channel_id: int,
    package_name: str | None,
    rebate_rate_bp: int,
    is_active: bool = True,
) -> PartnerPolicy:
    normalized_package = str(package_name or "").strip()
    if normalized_package in {"*", "ALL", "all"}:
        normalized_package = ""
    package_key = normalized_package or None
    rate = _normalize_rebate_rate_bp(rebate_rate_bp)
    row = (
        db.query(PartnerPolicy)
        .filter(PartnerPolicy.channel_id == channel_id, PartnerPolicy.package_name == package_key)
        .with_for_update()
        .first()
    )
    if row is None:
        row = PartnerPolicy(
            channel_id=channel_id,
            package_name=package_key,
            rebate_rate_bp=rate,
            is_active=bool(is_active),
        )
        db.add(row)
    else:
        row.rebate_rate_bp = rate
        row.is_active = bool(is_active)
    db.flush()
    return row


def _resolve_rate_by_policy(db: Session, *, channel: PartnerChannel, package_name: str | None) -> int:
    normalized_package = str(package_name or "").strip()
    if normalized_package:
        exact = (
            db.query(PartnerPolicy)
            .filter(
                PartnerPolicy.channel_id == channel.id,
                PartnerPolicy.is_active.is_(True),
                PartnerPolicy.package_name == normalized_package,
            )
            .order_by(desc(PartnerPolicy.id))
            .first()
        )
        if exact is not None:
            return _normalize_rebate_rate_bp(exact.rebate_rate_bp)
    default_row = (
        db.query(PartnerPolicy)
        .filter(
            PartnerPolicy.channel_id == channel.id,
            PartnerPolicy.is_active.is_(True),
            PartnerPolicy.package_name.is_(None),
        )
        .order_by(desc(PartnerPolicy.id))
        .first()
    )
    if default_row is not None:
        return _normalize_rebate_rate_bp(default_row.rebate_rate_bp)
    return _normalize_rebate_rate_bp(channel.default_rebate_rate_bp)


def _read_tracking_inputs(
    request: Request | None,
    *,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
) -> tuple[str, str]:
    code = _normalize_channel_code(explicit_channel_code)
    token = str(explicit_channel_token or "").strip()
    if request is not None:
        if not code:
            code = _normalize_channel_code(request.query_params.get("ch") or request.headers.get("x-partner-channel"))
        if not token:
            token = str(request.query_params.get("ck") or request.headers.get("x-partner-token") or "").strip()
    return code, token


def _find_active_channel_by_code_token(db: Session, *, channel_code: str, channel_token: str) -> PartnerChannel | None:
    if not channel_code or not channel_token:
        return None
    row = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.channel_code == channel_code, PartnerChannel.status == "active")
        .first()
    )
    if row is None:
        return None
    return row if row.order_token == channel_token else None


def _resolve_bound_channel(db: Session, *, user_id: int) -> PartnerChannel | None:
    binding = db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == user_id).first()
    if binding is None:
        return None
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == binding.channel_id).first()
    if channel is None or channel.status != "active":
        return None
    return channel


def _upsert_user_binding(
    db: Session,
    *,
    user_id: int,
    channel_id: int,
    bind_source: str,
    force_rebind: bool = False,
) -> PartnerUserBinding:
    row = db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == user_id).with_for_update().first()
    if row is None:
        row = PartnerUserBinding(user_id=user_id, channel_id=channel_id, bind_source=bind_source[:24] or "link")
        db.add(row)
        db.flush()
        return row
    if row.channel_id == channel_id:
        row.bind_source = bind_source[:24] or row.bind_source
        db.flush()
        return row

    current_channel = db.query(PartnerChannel).filter(PartnerChannel.id == row.channel_id).first()
    if force_rebind or current_channel is None or current_channel.status != "active":
        row.channel_id = channel_id
        row.bind_source = bind_source[:24] or row.bind_source
        db.flush()
    return row


def resolve_partner_channel_for_order(
    db: Session,
    *,
    request: Request | None,
    user_id: int,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
) -> tuple[PartnerChannel | None, str]:
    channel_code, channel_token = _read_tracking_inputs(
        request,
        explicit_channel_code=explicit_channel_code,
        explicit_channel_token=explicit_channel_token,
    )
    if channel_code and channel_token:
        linked_channel = _find_active_channel_by_code_token(db, channel_code=channel_code, channel_token=channel_token)
        if linked_channel is not None:
            _upsert_user_binding(
                db,
                user_id=user_id,
                channel_id=linked_channel.id,
                bind_source="link",
                force_rebind=True,
            )
            return linked_channel, "link"
    bound = _resolve_bound_channel(db, user_id=user_id)
    if bound is not None:
        return bound, "binding"
    return None, ""


def attach_order_attribution_from_request(
    db: Session,
    *,
    request: Request | None,
    user_id: int,
    order: Order,
    package_name: str | None = None,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
) -> PartnerOrderAttribution | None:
    existing = db.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    if existing is not None:
        return existing

    channel, source = resolve_partner_channel_for_order(
        db,
        request=request,
        user_id=user_id,
        explicit_channel_code=explicit_channel_code,
        explicit_channel_token=explicit_channel_token,
    )
    if channel is None:
        return None
    rate_bp = _resolve_rate_by_policy(db, channel=channel, package_name=package_name)
    row = PartnerOrderAttribution(
        order_id=order.id,
        order_no=order.order_no,
        user_id=user_id,
        channel_id=channel.id,
        channel_code_snapshot=channel.channel_code,
        package_name=str(package_name or "").strip()[:64],
        rebate_rate_bp=rate_bp,
        attribution_source=source or "binding",
    )
    db.add(row)
    db.flush()
    return row


def _ensure_order_attribution_by_binding(db: Session, *, order: Order) -> PartnerOrderAttribution | None:
    existing = db.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    if existing is not None:
        return existing
    channel = _resolve_bound_channel(db, user_id=order.user_id)
    if channel is None:
        return None
    rate_bp = _resolve_rate_by_policy(db, channel=channel, package_name=None)
    row = PartnerOrderAttribution(
        order_id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        channel_id=channel.id,
        channel_code_snapshot=channel.channel_code,
        package_name="",
        rebate_rate_bp=rate_bp,
        attribution_source="binding",
    )
    db.add(row)
    db.flush()
    return row


def _task_rebate_order_no(task_id: int) -> str:
    return f"TASK:{int(task_id)}"


def record_task_consume_rebate(
    db: Session,
    *,
    task_id: int,
    user_id: int,
    cost_fen: int,
    task_type: str = "",
) -> PartnerRebateLedger | None:
    consumed_fen = int(cost_fen or 0)
    if consumed_fen <= 0:
        return None
    channel = _resolve_bound_channel(db, user_id=user_id)
    if channel is None:
        return None
    order_no = _task_rebate_order_no(task_id)
    existing = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.order_no == order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .first()
    )
    if existing is not None:
        return existing
    rate_bp = _resolve_rate_by_policy(db, channel=channel, package_name=None)
    rebate_amount_fen = max((consumed_fen * _normalize_rebate_rate_bp(rate_bp) + 5000) // 10000, 0)
    if rebate_amount_fen <= 0:
        return None
    ledger = PartnerRebateLedger(
        channel_id=channel.id,
        order_id=None,
        order_no=order_no,
        user_id=user_id,
        entry_type=PartnerLedgerEntryType.ACCRUAL,
        status=PartnerLedgerStatus.PENDING,
        base_amount_fen=consumed_fen,
        rebate_amount_fen=rebate_amount_fen,
        statement_month=_statement_month_now(),
        note=f"任务消费返佣:{task_type or 'task'}:{task_id}",
    )
    db.add(ledger)
    db.flush()
    return ledger


def record_task_refund_rebate(db: Session, *, task_id: int, operator: str = "") -> PartnerRebateLedger | None:
    order_no = _task_rebate_order_no(task_id)
    accrual = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .order_by(desc(PartnerRebateLedger.id))
        .first()
    )
    if accrual is None:
        return None
    existing = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.REVERSAL,
        )
        .first()
    )
    if existing is not None:
        return existing
    reversal = PartnerRebateLedger(
        channel_id=accrual.channel_id,
        order_id=accrual.order_id,
        order_no=accrual.order_no,
        user_id=accrual.user_id,
        entry_type=PartnerLedgerEntryType.REVERSAL,
        status=PartnerLedgerStatus.PENDING,
        base_amount_fen=accrual.base_amount_fen,
        rebate_amount_fen=-abs(int(accrual.rebate_amount_fen or 0)),
        statement_month=_statement_month_now(),
        related_ledger_id=accrual.id,
        note=f"任务退款冲正:{task_id}" + (f" [{operator}]" if operator else ""),
    )
    db.add(reversal)
    db.flush()
    return reversal


def record_paid_order_rebate(db: Session, *, order: Order) -> PartnerRebateLedger | None:
    if str(order.status or "").lower() != "paid":
        return None
    existing = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order.order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .first()
    )
    if existing is not None:
        return existing

    attribution = _ensure_order_attribution_by_binding(db, order=order)
    if attribution is None:
        return None

    base_amount_fen = int(cny_to_fen(order.amount_cny))
    rate_bp = _normalize_rebate_rate_bp(attribution.rebate_rate_bp)
    rebate_amount_fen = max((base_amount_fen * rate_bp + 5000) // 10000, 0)
    if rebate_amount_fen <= 0:
        return None

    ledger = PartnerRebateLedger(
        channel_id=attribution.channel_id,
        order_id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        entry_type=PartnerLedgerEntryType.ACCRUAL,
        status=PartnerLedgerStatus.PENDING,
        base_amount_fen=base_amount_fen,
        rebate_amount_fen=rebate_amount_fen,
        statement_month=_statement_month_now(),
        note=f"订单支付返佣:{order.order_no}",
    )
    db.add(ledger)
    db.flush()
    return ledger


def record_refund_order_rebate(db: Session, *, order: Order, operator: str = "") -> PartnerRebateLedger | None:
    accrual = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order.order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .order_by(desc(PartnerRebateLedger.id))
        .first()
    )
    if accrual is None:
        return None
    existing = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order.order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.REVERSAL,
        )
        .first()
    )
    if existing is not None:
        return existing
    reversal = PartnerRebateLedger(
        channel_id=accrual.channel_id,
        order_id=accrual.order_id,
        order_no=accrual.order_no,
        user_id=accrual.user_id,
        entry_type=PartnerLedgerEntryType.REVERSAL,
        status=PartnerLedgerStatus.PENDING,
        base_amount_fen=accrual.base_amount_fen,
        rebate_amount_fen=-abs(int(accrual.rebate_amount_fen or 0)),
        statement_month=_statement_month_now(),
        related_ledger_id=accrual.id,
        note=f"订单退款冲正:{order.order_no}" + (f" [{operator}]" if operator else ""),
    )
    db.add(reversal)
    db.flush()
    return reversal


def _sum_withdraw_amount_fen(db: Session, *, channel_id: int, statuses: tuple[PartnerWithdrawStatus, ...]) -> int:
    if not statuses:
        return 0
    value = (
        db.query(func.coalesce(func.sum(PartnerWithdrawRequest.apply_amount_fen), 0))
        .filter(
            PartnerWithdrawRequest.channel_id == channel_id,
            PartnerWithdrawRequest.status.in_(list(statuses)),
        )
        .scalar()
        or 0
    )
    return int(value)


def compute_partner_withdrawable_fen(db: Session, *, channel_id: int) -> dict:
    settled_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel_id,
            PartnerRebateLedger.status == PartnerLedgerStatus.SETTLED,
        )
        .scalar()
        or 0
    )
    pending_apply_fen = _sum_withdraw_amount_fen(db, channel_id=channel_id, statuses=(PartnerWithdrawStatus.PENDING,))
    approved_apply_fen = _sum_withdraw_amount_fen(db, channel_id=channel_id, statuses=(PartnerWithdrawStatus.APPROVED,))
    paid_fen = _sum_withdraw_amount_fen(db, channel_id=channel_id, statuses=(PartnerWithdrawStatus.PAID,))
    reserved_fen = pending_apply_fen + approved_apply_fen
    withdrawable_fen = max(int(settled_rebate_fen) - int(reserved_fen) - int(paid_fen), 0)
    return {
        "settled_rebate_fen": int(settled_rebate_fen),
        "withdrawable_fen": int(withdrawable_fen),
        "pending_apply_fen": int(pending_apply_fen),
        "approved_apply_fen": int(approved_apply_fen),
        "paid_fen": int(paid_fen),
    }


def create_partner_withdraw_request(
    db: Session,
    *,
    channel: PartnerChannel,
    apply_amount_fen: int,
    note: str = "",
) -> PartnerWithdrawRequest:
    normalized_amount = int(apply_amount_fen or 0)
    if normalized_amount < 10000:
        raise BizError(code=4471, message="提现金额需至少 100 元")
    summary = compute_partner_withdrawable_fen(db, channel_id=channel.id)
    if normalized_amount > int(summary["withdrawable_fen"]):
        raise BizError(code=4472, message="可提现余额不足")
    request_no = f"WD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
    row = PartnerWithdrawRequest(
        request_no=request_no,
        channel_id=channel.id,
        apply_amount_fen=normalized_amount,
        status=PartnerWithdrawStatus.PENDING,
        note=str(note or "").strip()[:255],
    )
    db.add(row)
    db.flush()
    return row


def review_partner_withdraw_request(
    db: Session,
    *,
    request_id: int,
    admin_id: int,
    approve: bool,
    reject_reason: str = "",
) -> PartnerWithdrawRequest:
    row = db.query(PartnerWithdrawRequest).filter(PartnerWithdrawRequest.id == request_id).with_for_update().first()
    if row is None:
        raise BizError(code=4473, message="提现申请不存在", http_status=404)
    if row.status != PartnerWithdrawStatus.PENDING:
        return row
    if approve:
        row.status = PartnerWithdrawStatus.APPROVED
        row.reject_reason = ""
    else:
        reason = str(reject_reason or "").strip()
        if not reason:
            raise BizError(code=4474, message="驳回需填写原因")
        row.status = PartnerWithdrawStatus.REJECTED
        row.reject_reason = reason[:255]
    row.reviewed_by = int(admin_id)
    row.reviewed_at = datetime.utcnow()
    db.flush()
    return row


def mark_partner_withdraw_paid(
    db: Session,
    *,
    request_id: int,
    admin_id: int,
) -> PartnerWithdrawRequest:
    row = db.query(PartnerWithdrawRequest).filter(PartnerWithdrawRequest.id == request_id).with_for_update().first()
    if row is None:
        raise BizError(code=4473, message="提现申请不存在", http_status=404)
    if row.status == PartnerWithdrawStatus.PAID:
        return row
    if row.status != PartnerWithdrawStatus.APPROVED:
        raise BizError(code=4475, message="仅审核通过的申请可标记打款")
    row.status = PartnerWithdrawStatus.PAID
    row.paid_at = datetime.utcnow()
    row.reviewed_by = int(admin_id)
    if row.reviewed_at is None:
        row.reviewed_at = datetime.utcnow()
    db.flush()
    return row


def generate_monthly_statement(
    db: Session,
    *,
    channel_id: int,
    statement_month: str,
) -> tuple[PartnerMonthlyStatement, bool]:
    month_key = _normalize_statement_month(statement_month)
    row = (
        db.query(PartnerMonthlyStatement)
        .filter(
            PartnerMonthlyStatement.channel_id == channel_id,
            PartnerMonthlyStatement.statement_month == month_key,
        )
        .with_for_update()
        .first()
    )
    if row is not None:
        return row, False

    pending_rows = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.channel_id == channel_id,
            PartnerRebateLedger.statement_month == month_key,
            PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
            PartnerRebateLedger.entry_type.in_([PartnerLedgerEntryType.ACCRUAL, PartnerLedgerEntryType.REVERSAL]),
        )
        .all()
    )
    accrual_rows = [item for item in pending_rows if item.entry_type == PartnerLedgerEntryType.ACCRUAL]
    row = PartnerMonthlyStatement(
        channel_id=channel_id,
        statement_month=month_key,
        status=PartnerStatementStatus.GENERATED,
        total_orders=len({str(item.order_no or "") for item in accrual_rows if item.order_no}),
        gross_amount_fen=sum(int(item.base_amount_fen or 0) for item in accrual_rows),
        rebate_amount_fen=sum(int(item.rebate_amount_fen or 0) for item in pending_rows),
    )
    db.add(row)
    db.flush()
    for item in pending_rows:
        item.statement_id = row.id
    db.flush()
    return row, True


def settle_monthly_statement(
    db: Session,
    *,
    statement_id: int,
    admin_id: int,
) -> tuple[PartnerMonthlyStatement, bool]:
    row = db.query(PartnerMonthlyStatement).filter(PartnerMonthlyStatement.id == statement_id).with_for_update().first()
    if row is None:
        raise BizError(code=4468, message="结算单不存在", http_status=404)
    if row.status == PartnerStatementStatus.SETTLED:
        return row, True
    settled_at = datetime.utcnow()
    row.status = PartnerStatementStatus.SETTLED
    row.settled_by = admin_id
    row.settled_at = settled_at
    db.query(PartnerRebateLedger).filter(
        PartnerRebateLedger.statement_id == row.id,
        PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
    ).update(
        {
            PartnerRebateLedger.status: PartnerLedgerStatus.SETTLED,
            PartnerRebateLedger.settled_at: settled_at,
        },
        synchronize_session=False,
    )
    db.flush()
    return row, False


def authenticate_partner_portal(db: Session, *, channel_code: str, portal_token: str) -> PartnerChannel:
    normalized_code = _normalize_channel_code(channel_code)
    normalized_token = str(portal_token or "").strip()
    if not normalized_code or not normalized_token:
        raise BizError(code=4469, message="渠道访问参数缺失")
    channel = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.channel_code == normalized_code, PartnerChannel.status == "active")
        .first()
    )
    if channel is None or channel.portal_token != normalized_token:
        raise BizError(code=4470, message="渠道访问凭证无效", http_status=403)
    return channel


def get_partner_portal_overview(db: Session, *, channel: PartnerChannel, statement_month: str | None = None) -> dict:
    month_key = _normalize_statement_month(statement_month) if statement_month else _statement_month_now()
    pending_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
        )
        .scalar()
        or 0
    )
    settled_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.status == PartnerLedgerStatus.SETTLED,
        )
        .scalar()
        or 0
    )
    month_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.statement_month == month_key,
        )
        .scalar()
        or 0
    )
    month_order_count = (
        db.query(func.count(func.distinct(PartnerRebateLedger.order_no)))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.statement_month == month_key,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .scalar()
        or 0
    )
    withdraw_summary = compute_partner_withdrawable_fen(db, channel_id=channel.id)
    return {
        "channel_id": channel.id,
        "channel_code": channel.channel_code,
        "channel_name": channel.name,
        "statement_month": month_key,
        "month_order_count": int(month_order_count),
        "month_rebate_fen": int(month_rebate_fen),
        "pending_rebate_fen": int(pending_rebate_fen),
        "settled_rebate_fen": int(settled_rebate_fen),
        "withdrawable_fen": int(withdraw_summary["withdrawable_fen"]),
        "pending_withdraw_fen": int(withdraw_summary["pending_apply_fen"]),
        "approved_withdraw_fen": int(withdraw_summary["approved_apply_fen"]),
        "paid_withdraw_fen": int(withdraw_summary["paid_fen"]),
    }
