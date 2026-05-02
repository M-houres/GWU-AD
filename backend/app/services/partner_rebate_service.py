from __future__ import annotations

from datetime import datetime
import hashlib
import hmac
import re
import secrets
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy import desc, func, or_
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
from app.security import hash_password, verify_password

settings = get_settings()

_CHANNEL_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,31}$")
_STATEMENT_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
MAX_PARTNER_LEVEL = 2


def _normalize_channel_code(value: str | None) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    return re.sub(r"[^A-Z0-9_-]", "", raw)[:32]


def _normalize_channel_scene(value: str | None) -> str:
    return re.sub(r"[^a-z0-9_-]", "", str(value or "").strip().lower())[:64]


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


def generate_partner_portal_password() -> str:
    return f"Gw{secrets.token_urlsafe(8)}!9a"


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


def _frontend_base_url(request: Request | None = None) -> str:
    raw = str(settings.frontend_base_url or "").strip()
    if raw:
        return raw.split("/api/", 1)[0].rstrip("/")
    preferred_base = "https://restin.top"
    if request is not None:
        origin = str(request.headers.get("origin") or "").strip()
        referer = str(request.headers.get("referer") or "").strip()
        candidate = origin or referer
        if candidate:
            parsed = urlparse(candidate)
            if parsed.scheme and parsed.netloc and "restin.top" in parsed.netloc.lower():
                return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
        if forwarded_host and "restin.top" in forwarded_host.lower():
            scheme = forwarded_proto or request.url.scheme or "https"
            return f"{scheme}://{forwarded_host}".rstrip("/")
    return preferred_base


def build_channel_links(channel: PartnerChannel, request: Request | None = None) -> dict[str, str]:
    frontend_base = _frontend_base_url(request)
    miniapp_order_path = f"/pages/home/index?ch={channel.channel_code}&ck={channel.order_token}"
    portal_query = f"account={channel.channel_code}"
    return {
        "order_link": f"{frontend_base}/app/detect?ch={channel.channel_code}&ck={channel.order_token}",
        "portal_link": f"{frontend_base}/app/partner/login?{portal_query}",
        "portal_login_link": f"{frontend_base}/app/partner/login?{portal_query}",
        "miniapp_order_path": miniapp_order_path,
    }


def build_channel_scene_value(channel: PartnerChannel) -> str:
    payload = f"pch{int(channel.id)}"
    secret = str(settings.jwt_secret or "gw-partner-scene")
    sign = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:12]
    return f"{payload}s{sign}"


def resolve_channel_by_scene(db: Session, channel_scene: str | None) -> PartnerChannel | None:
    normalized = _normalize_channel_scene(channel_scene)
    matched = re.fullmatch(r"pch(\d+)s([a-f0-9]{12})", normalized)
    if matched is None:
        return None
    channel_id = int(matched.group(1) or 0)
    if channel_id <= 0:
        return None
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id, PartnerChannel.status == "active").first()
    if channel is None:
        return None
    return channel if build_channel_scene_value(channel) == normalized else None


def _ensure_valid_parent(
    db: Session,
    *,
    parent_channel_id: int | None,
) -> tuple[PartnerChannel | None, int, int | None]:
    if not parent_channel_id:
        return None, 1, None
    parent = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.id == int(parent_channel_id))
        .with_for_update()
        .first()
    )
    if parent is None:
        raise BizError(code=4476, message="上级渠道不存在")
    parent_level = int(parent.level or 1)
    level = parent_level + 1
    if level > MAX_PARTNER_LEVEL:
        raise BizError(code=4477, message="分销层级最多支持 2 级")
    root_channel_id = int(parent.root_channel_id or parent.id)
    return parent, level, root_channel_id


def _resolve_channel_chain(db: Session, *, channel_id: int) -> list[PartnerChannel]:
    chain: list[PartnerChannel] = []
    visited: set[int] = set()
    current_id = int(channel_id or 0)
    while current_id > 0 and current_id not in visited:
        visited.add(current_id)
        current = db.query(PartnerChannel).filter(PartnerChannel.id == current_id).first()
        if current is None or current.status != "active":
            break
        chain.append(current)
        current_id = int(current.parent_channel_id or 0)
        if len(chain) >= MAX_PARTNER_LEVEL:
            break
    return chain


def _compute_chain_rate_plan(db: Session, *, direct_channel: PartnerChannel, package_name: str | None) -> list[tuple[PartnerChannel, int]]:
    chain = _resolve_channel_chain(db, channel_id=direct_channel.id)
    if not chain:
        return []
    direct_rate = _resolve_rate_by_policy(db, channel=chain[0], package_name=package_name)
    if direct_rate <= 0:
        return []
    plan: list[tuple[PartnerChannel, int]] = [(chain[0], direct_rate)]
    child_rate = direct_rate
    for channel in chain[1:]:
        parent_rate = _resolve_rate_by_policy(db, channel=channel, package_name=package_name)
        parent_delta = max(parent_rate - child_rate, 0)
        if parent_delta > 0:
            plan.append((channel, parent_delta))
        child_rate = max(child_rate, parent_rate)
    return plan


def _serialize_rebate_plan(plan: list[tuple[PartnerChannel, int]]) -> list[dict]:
    serialized: list[dict] = []
    for channel, rate_bp in plan:
        channel_id = int(channel.id or 0)
        if channel_id <= 0:
            continue
        serialized.append(
            {
                "channel_id": channel_id,
                "level": int(channel.level or 1),
                "rate_bp": _normalize_rebate_rate_bp(rate_bp),
                "channel_code": str(channel.channel_code or ""),
            }
        )
    return serialized


def _deserialize_rebate_plan(db: Session, *, payload) -> list[tuple[PartnerChannel, int]]:
    if not isinstance(payload, list):
        return []
    plan: list[tuple[PartnerChannel, int]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        channel_id = int(item.get("channel_id") or 0)
        if channel_id <= 0:
            continue
        channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).first()
        if channel is None or channel.status != "active":
            continue
        plan.append((channel, _normalize_rebate_rate_bp(item.get("rate_bp"))))
    return plan


def _set_attribution_snapshot(
    db: Session,
    *,
    attribution: PartnerOrderAttribution,
    channel: PartnerChannel,
    package_name: str | None,
) -> None:
    rate_bp = _resolve_rate_by_policy(db, channel=channel, package_name=package_name)
    rebate_plan = _compute_chain_rate_plan(db, direct_channel=channel, package_name=package_name)
    attribution.rebate_rate_bp = rate_bp
    attribution.package_name = str(package_name or "").strip()[:64]
    root_channel = db.query(PartnerChannel).filter(PartnerChannel.id == int(channel.root_channel_id or channel.id)).first()
    attribution.root_channel_code_snapshot = str(root_channel.channel_code if root_channel else channel.channel_code)


def _order_partner_snapshot(order: Order) -> dict:
    snapshot = order.package_snapshot if isinstance(order.package_snapshot, dict) else {}
    partner_snapshot = snapshot.get("partner_snapshot")
    return partner_snapshot if isinstance(partner_snapshot, dict) else {}


def _write_order_partner_snapshot(
    order: Order,
    *,
    attribution: PartnerOrderAttribution,
    rebate_plan: list[tuple[PartnerChannel, int]],
) -> None:
    snapshot = dict(order.package_snapshot or {}) if isinstance(order.package_snapshot, dict) else {}
    snapshot["partner_snapshot"] = {
        "channel_id": int(attribution.channel_id or 0),
        "channel_code": str(attribution.channel_code_snapshot or ""),
        "root_channel_id": int(attribution.root_channel_id or 0),
        "root_channel_code": str(attribution.root_channel_code_snapshot or ""),
        "package_name": str(attribution.package_name or ""),
        "rebate_rate_bp": int(attribution.rebate_rate_bp or 0),
        "rebate_plan": _serialize_rebate_plan(rebate_plan),
    }
    order.package_snapshot = snapshot


def _rebuild_legacy_rebate_plan(
    db: Session,
    *,
    attribution: PartnerOrderAttribution,
    direct_channel: PartnerChannel,
) -> list[tuple[PartnerChannel, int]]:
    direct_rate = _normalize_rebate_rate_bp(attribution.rebate_rate_bp)
    if direct_rate <= 0:
        return []
    plan: list[tuple[PartnerChannel, int]] = [(direct_channel, direct_rate)]
    parent_id = int(direct_channel.parent_channel_id or 0)
    if parent_id <= 0:
        return plan
    parent_channel = db.query(PartnerChannel).filter(PartnerChannel.id == parent_id).first()
    if parent_channel is None or parent_channel.status != "active":
        return plan
    package_name = str(attribution.package_name or "").strip() or None
    parent_rate = _resolve_rate_by_policy(db, channel=parent_channel, package_name=package_name)
    parent_delta = max(_normalize_rebate_rate_bp(parent_rate) - direct_rate, 0)
    if parent_delta > 0:
        plan.append((parent_channel, parent_delta))
    return plan


def _ensure_order_partner_snapshot(
    db: Session,
    *,
    order: Order,
    attribution: PartnerOrderAttribution,
    direct_channel: PartnerChannel,
) -> list[tuple[PartnerChannel, int]]:
    snapshot_plan = _resolve_rebate_plan_for_order_snapshot(db, order=order)
    if snapshot_plan:
        return snapshot_plan
    rebate_plan = _rebuild_legacy_rebate_plan(
        db,
        attribution=attribution,
        direct_channel=direct_channel,
    )
    if rebate_plan:
        _write_order_partner_snapshot(order, attribution=attribution, rebate_plan=rebate_plan)
        db.flush()
    return rebate_plan


def _resolve_rebate_plan_for_order_snapshot(db: Session, *, order: Order) -> list[tuple[PartnerChannel, int]]:
    partner_snapshot = _order_partner_snapshot(order)
    snapshot_plan = _deserialize_rebate_plan(db, payload=partner_snapshot.get("rebate_plan"))
    if snapshot_plan:
        return snapshot_plan
    return []


def _create_missing_reversal_rows(
    db: Session,
    *,
    accrual_rows: list[PartnerRebateLedger],
    statement_month: str,
    note_prefix: str,
) -> PartnerRebateLedger | None:
    existing_related_ids = {
        int(row[0])
        for row in db.query(PartnerRebateLedger.related_ledger_id)
        .filter(
            PartnerRebateLedger.related_ledger_id.is_not(None),
            PartnerRebateLedger.related_ledger_id.in_([int(item.id) for item in accrual_rows if int(item.id or 0) > 0]),
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.REVERSAL,
        )
        .all()
        if int(row[0] or 0) > 0
    }
    created: PartnerRebateLedger | None = None
    for accrual_row in accrual_rows:
        if int(accrual_row.id or 0) in existing_related_ids:
            continue
        reversal = PartnerRebateLedger(
            channel_id=accrual_row.channel_id,
            source_channel_id=accrual_row.source_channel_id,
            order_id=accrual_row.order_id,
            order_no=accrual_row.order_no,
            user_id=accrual_row.user_id,
            entry_type=PartnerLedgerEntryType.REVERSAL,
            status=PartnerLedgerStatus.PENDING,
            base_amount_fen=accrual_row.base_amount_fen,
            rebate_rate_bp=int(accrual_row.rebate_rate_bp or 0),
            rebate_amount_fen=-abs(int(accrual_row.rebate_amount_fen or 0)),
            source_channel_code_snapshot=accrual_row.source_channel_code_snapshot,
            statement_month=statement_month,
            related_ledger_id=accrual_row.id,
            note=note_prefix,
        )
        db.add(reversal)
        db.flush()
        if created is None:
            created = reversal
    return created


def _direct_child_channels(db: Session, *, channel_id: int) -> list[PartnerChannel]:
    return (
        db.query(PartnerChannel)
        .filter(PartnerChannel.parent_channel_id == channel_id)
        .order_by(PartnerChannel.id.asc())
        .all()
    )


def _active_package_policies(db: Session, *, channel_id: int) -> list[PartnerPolicy]:
    return (
        db.query(PartnerPolicy)
        .filter(
            PartnerPolicy.channel_id == channel_id,
            PartnerPolicy.is_active.is_(True),
            PartnerPolicy.package_name.is_not(None),
        )
        .order_by(PartnerPolicy.id.asc())
        .all()
    )


def _upsert_default_partner_policy(db: Session, *, channel_id: int, rebate_rate_bp: int) -> PartnerPolicy:
    rate = _normalize_rebate_rate_bp(rebate_rate_bp)
    row = (
        db.query(PartnerPolicy)
        .filter(PartnerPolicy.channel_id == channel_id, PartnerPolicy.package_name.is_(None))
        .with_for_update()
        .first()
    )
    if row is None:
        row = PartnerPolicy(
            channel_id=channel_id,
            package_name=None,
            rebate_rate_bp=rate,
            is_active=True,
        )
        db.add(row)
    else:
        row.rebate_rate_bp = rate
        row.is_active = True
    db.flush()
    return row


def _assert_direct_children_within_default_rate(
    db: Session,
    *,
    channel: PartnerChannel,
    new_default_rate_bp: int,
) -> None:
    ceiling_rate = _normalize_rebate_rate_bp(new_default_rate_bp)
    for child in _direct_child_channels(db, channel_id=int(channel.id)):
        child_default_rate = _resolve_rate_by_policy(db, channel=child, package_name=None)
        if child_default_rate > ceiling_rate:
            raise BizError(code=4479, message=f"下级渠道 {child.name} 的默认返佣比例高于当前上限")
        for child_policy in _active_package_policies(db, channel_id=int(child.id)):
            parent_package_rate = _resolve_rate_by_policy(db, channel=channel, package_name=child_policy.package_name)
            if _normalize_rebate_rate_bp(child_policy.rebate_rate_bp) > parent_package_rate:
                raise BizError(code=4480, message=f"下级渠道 {child.name} 的套餐策略超出当前上限")


def _assert_direct_children_within_package_rate(
    db: Session,
    *,
    channel: PartnerChannel,
    package_name: str,
    new_rate_bp: int,
) -> None:
    normalized_package = str(package_name or "").strip()
    ceiling_rate = _normalize_rebate_rate_bp(new_rate_bp)
    if not normalized_package:
        return
    for child in _direct_child_channels(db, channel_id=int(channel.id)):
        child_rate = _resolve_rate_by_policy(db, channel=child, package_name=normalized_package)
        if child_rate > ceiling_rate:
            raise BizError(code=4480, message=f"下级渠道 {child.name} 的套餐策略超出当前上限")


def _resulting_package_rate(
    db: Session,
    *,
    channel: PartnerChannel,
    package_name: str,
    proposed_rate_bp: int,
    proposed_is_active: bool,
) -> int:
    if proposed_is_active:
        return _normalize_rebate_rate_bp(proposed_rate_bp)
    return _resolve_rate_by_policy(db, channel=channel, package_name=None)


def create_partner_channel(
    db: Session,
    *,
    name: str,
    contact_name: str = "",
    contact_phone: str = "",
    channel_code: str | None = None,
    rebate_rate_bp: int = 1500,
    parent_channel_id: int | None = None,
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

    parent, level, root_channel_id = _ensure_valid_parent(db, parent_channel_id=parent_channel_id)
    normalized_rate = _normalize_rebate_rate_bp(rebate_rate_bp)
    if parent is not None:
        parent_rate = _resolve_rate_by_policy(db, channel=parent, package_name=None)
        if normalized_rate > parent_rate:
            raise BizError(code=4478, message="下级返佣比例不能高于上级默认比例")

    channel = PartnerChannel(
        channel_code=normalized_code,
        parent_channel_id=int(parent.id) if parent is not None else None,
        root_channel_id=root_channel_id,
        level=level,
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
    if channel.root_channel_id is None:
        channel.root_channel_id = channel.id
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
        normalized_rate = _normalize_rebate_rate_bp(rebate_rate_bp)
        if channel.parent_channel_id:
            parent = db.query(PartnerChannel).filter(PartnerChannel.id == channel.parent_channel_id).first()
            if parent is not None:
                parent_rate = _resolve_rate_by_policy(db, channel=parent, package_name=None)
                if normalized_rate > parent_rate:
                    raise BizError(code=4478, message="下级返佣比例不能高于上级默认比例")
        _assert_direct_children_within_default_rate(
            db,
            channel=channel,
            new_default_rate_bp=normalized_rate,
        )
        channel.default_rebate_rate_bp = normalized_rate
        _upsert_default_partner_policy(db, channel_id=int(channel.id), rebate_rate_bp=normalized_rate)
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
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).with_for_update().first()
    if channel is None:
        raise BizError(code=4476, message="渠道不存在")
    if package_key is None and not is_active:
        raise BizError(code=4481, message="默认返佣策略必须保持启用")
    if channel.parent_channel_id:
        parent = db.query(PartnerChannel).filter(PartnerChannel.id == channel.parent_channel_id).first()
        if parent is not None and bool(is_active):
            parent_rate = _resolve_rate_by_policy(db, channel=parent, package_name=package_key)
            if rate > parent_rate:
                raise BizError(code=4478, message="下级返佣比例不能高于上级默认比例")
    if package_key is None:
        if bool(is_active):
            _assert_direct_children_within_default_rate(
                db,
                channel=channel,
                new_default_rate_bp=rate,
            )
        channel.default_rebate_rate_bp = rate
        db.flush()
    else:
        effective_parent_rate = _resulting_package_rate(
            db,
            channel=channel,
            package_name=package_key,
            proposed_rate_bp=rate,
            proposed_is_active=bool(is_active),
        )
        _assert_direct_children_within_package_rate(
            db,
            channel=channel,
            package_name=package_key,
            new_rate_bp=effective_parent_rate,
        )
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
    db: Session | None,
    request: Request | None,
    *,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
    explicit_channel_scene: str | None = None,
) -> tuple[str, str]:
    code = _normalize_channel_code(explicit_channel_code)
    token = str(explicit_channel_token or "").strip()
    scene = _normalize_channel_scene(explicit_channel_scene)
    if request is not None:
        if not scene:
            scene = _normalize_channel_scene(request.query_params.get("cs") or request.headers.get("x-partner-scene"))
        if not code:
            code = _normalize_channel_code(request.query_params.get("ch") or request.headers.get("x-partner-channel"))
        if not token:
            token = str(request.query_params.get("ck") or request.headers.get("x-partner-token") or "").strip()
    if (not code or not token) and scene and db is not None:
        channel = resolve_channel_by_scene(db, scene)
        if channel is not None:
            code = str(channel.channel_code or "")
            token = str(channel.order_token or "")
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


def get_bound_channel_payload(db: Session, *, user_id: int) -> dict | None:
    binding = db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == user_id).first()
    if binding is None:
        return None
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == binding.channel_id).first()
    if channel is None:
        return None
    return {
        "channel_id": int(channel.id),
        "channel_code": str(channel.channel_code or ""),
        "channel_name": str(channel.name or ""),
        "channel_status": str(channel.status or ""),
        "bind_source": str(binding.bind_source or ""),
        "locked_at": binding.locked_at,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
        "active": bool(channel.status == "active"),
    }


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
        row = PartnerUserBinding(
            user_id=user_id,
            channel_id=channel_id,
            bind_source=bind_source[:24] or "link",
            locked_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
        return row
    if row.channel_id == channel_id:
        row.bind_source = bind_source[:24] or row.bind_source
        if row.locked_at is None:
            row.locked_at = datetime.utcnow()
        db.flush()
        return row

    current_channel = db.query(PartnerChannel).filter(PartnerChannel.id == row.channel_id).first()
    current_locked = row.locked_at is not None
    if force_rebind or not current_locked or current_channel is None or current_channel.status != "active":
        row.channel_id = channel_id
        row.bind_source = bind_source[:24] or row.bind_source
        row.locked_at = datetime.utcnow()
        db.flush()
    return row


def resolve_partner_channel_for_order(
    db: Session,
    *,
    request: Request | None,
    user_id: int,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
    explicit_channel_scene: str | None = None,
) -> tuple[PartnerChannel | None, str]:
    channel_code, channel_token = _read_tracking_inputs(
        db,
        request,
        explicit_channel_code=explicit_channel_code,
        explicit_channel_token=explicit_channel_token,
        explicit_channel_scene=explicit_channel_scene,
    )
    if channel_code and channel_token:
        linked_channel = _find_active_channel_by_code_token(db, channel_code=channel_code, channel_token=channel_token)
        if linked_channel is not None:
            binding = _upsert_user_binding(
                db,
                user_id=user_id,
                channel_id=linked_channel.id,
                bind_source="link",
                force_rebind=False,
            )
            if int(binding.channel_id or 0) == int(linked_channel.id):
                return linked_channel, "link"
    bound = _resolve_bound_channel(db, user_id=user_id)
    if bound is not None:
        return bound, "binding"
    return None, ""


def bind_partner_channel_from_request(
    db: Session,
    *,
    request: Request | None,
    user_id: int,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
    explicit_channel_scene: str | None = None,
    bind_source: str = "link",
    force_rebind: bool = False,
) -> PartnerChannel | None:
    channel_code, channel_token = _read_tracking_inputs(
        db,
        request,
        explicit_channel_code=explicit_channel_code,
        explicit_channel_token=explicit_channel_token,
        explicit_channel_scene=explicit_channel_scene,
    )
    if not channel_code or not channel_token:
        return _resolve_bound_channel(db, user_id=user_id)
    linked_channel = _find_active_channel_by_code_token(db, channel_code=channel_code, channel_token=channel_token)
    if linked_channel is None:
        return _resolve_bound_channel(db, user_id=user_id)
    binding = _upsert_user_binding(
        db,
        user_id=user_id,
        channel_id=linked_channel.id,
        bind_source=bind_source,
        force_rebind=force_rebind,
    )
    if int(binding.channel_id or 0) == int(linked_channel.id):
        return linked_channel
    return _resolve_bound_channel(db, user_id=user_id)


def bind_partner_channel(
    db: Session,
    *,
    user_id: int,
    channel_id: int,
    bind_source: str = "link",
    force_rebind: bool = False,
) -> PartnerChannel | None:
    channel = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.id == int(channel_id))
        .first()
    )
    if channel is None:
        return _resolve_bound_channel(db, user_id=user_id)
    binding = _upsert_user_binding(
        db,
        user_id=user_id,
        channel_id=int(channel.id),
        bind_source=bind_source,
        force_rebind=force_rebind,
    )
    if int(binding.channel_id or 0) == int(channel.id):
        return channel
    return _resolve_bound_channel(db, user_id=user_id)


def attach_order_attribution_from_request(
    db: Session,
    *,
    request: Request | None,
    user_id: int,
    order: Order,
    package_name: str | None = None,
    explicit_channel_code: str | None = None,
    explicit_channel_token: str | None = None,
    explicit_channel_scene: str | None = None,
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
        explicit_channel_scene=explicit_channel_scene,
    )
    if channel is None:
        return None
    row = PartnerOrderAttribution(
        order_id=order.id,
        order_no=order.order_no,
        user_id=user_id,
        channel_id=channel.id,
        root_channel_id=int(channel.root_channel_id or channel.id),
        channel_code_snapshot=channel.channel_code,
        root_channel_code_snapshot="",
        channel_level=int(channel.level or 1),
        package_name="",
        rebate_rate_bp=0,
        attribution_source=source or "binding",
    )
    _set_attribution_snapshot(
        db,
        attribution=row,
        channel=channel,
        package_name=package_name,
    )
    db.add(row)
    db.flush()
    _write_order_partner_snapshot(order, attribution=row, rebate_plan=_compute_chain_rate_plan(db, direct_channel=channel, package_name=package_name))
    db.flush()
    return row


def _ensure_order_attribution_by_binding(db: Session, *, order: Order) -> PartnerOrderAttribution | None:
    existing = db.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    if existing is not None:
        return existing
    channel = _resolve_bound_channel(db, user_id=order.user_id)
    if channel is None:
        return None
    row = PartnerOrderAttribution(
        order_id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        channel_id=channel.id,
        root_channel_id=int(channel.root_channel_id or channel.id),
        channel_code_snapshot=channel.channel_code,
        root_channel_code_snapshot="",
        channel_level=int(channel.level or 1),
        package_name="",
        rebate_rate_bp=0,
        attribution_source="binding",
    )
    _set_attribution_snapshot(
        db,
        attribution=row,
        channel=channel,
        package_name=None,
    )
    db.add(row)
    db.flush()
    _write_order_partner_snapshot(order, attribution=row, rebate_plan=_compute_chain_rate_plan(db, direct_channel=channel, package_name=None))
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
    plan = _compute_chain_rate_plan(db, direct_channel=channel, package_name=None)
    created: PartnerRebateLedger | None = None
    for target_channel, rate_bp in plan:
        rebate_amount_fen = max((consumed_fen * _normalize_rebate_rate_bp(rate_bp) + 5000) // 10000, 0)
        if rebate_amount_fen <= 0:
            continue
        ledger = PartnerRebateLedger(
            channel_id=target_channel.id,
            source_channel_id=channel.id,
            order_id=None,
            order_no=order_no,
            user_id=user_id,
            entry_type=PartnerLedgerEntryType.ACCRUAL,
            status=PartnerLedgerStatus.PENDING,
            base_amount_fen=consumed_fen,
            rebate_rate_bp=rate_bp,
            rebate_amount_fen=rebate_amount_fen,
            source_channel_code_snapshot=channel.channel_code,
            statement_month=_statement_month_now(),
            note=f"任务消费返佣:{task_type or 'task'}:{task_id}:L{int(target_channel.level or 1)}",
        )
        db.add(ledger)
        db.flush()
        if created is None:
            created = ledger
    return created


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
    accrual_rows = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .order_by(desc(PartnerRebateLedger.id))
        .all()
    )
    return _create_missing_reversal_rows(
        db,
        accrual_rows=accrual_rows,
        statement_month=_statement_month_now(),
        note_prefix=f"任务退款冲正:{task_id}" + (f" [{operator}]" if operator else ""),
    )


def record_paid_order_rebate(db: Session, *, order: Order) -> PartnerRebateLedger | None:
    if str(order.status or "").lower() != "paid":
        return None
    existing = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order.order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .order_by(desc(PartnerRebateLedger.id))
        .first()
    )
    if existing is not None:
        return existing

    attribution = db.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    if attribution is None:
        return None

    base_amount_fen = int(cny_to_fen(order.amount_cny))
    direct_channel = db.query(PartnerChannel).filter(PartnerChannel.id == attribution.channel_id).first()
    if direct_channel is None or direct_channel.status != "active":
        return None
    plan = _ensure_order_partner_snapshot(
        db,
        order=order,
        attribution=attribution,
        direct_channel=direct_channel,
    )
    created: PartnerRebateLedger | None = None
    for target_channel, rate_bp in plan:
        rebate_amount_fen = max((base_amount_fen * _normalize_rebate_rate_bp(rate_bp) + 5000) // 10000, 0)
        if rebate_amount_fen <= 0:
            continue
        ledger = PartnerRebateLedger(
            channel_id=target_channel.id,
            source_channel_id=direct_channel.id,
            order_id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            entry_type=PartnerLedgerEntryType.ACCRUAL,
            status=PartnerLedgerStatus.PENDING,
            base_amount_fen=base_amount_fen,
            rebate_rate_bp=rate_bp,
            rebate_amount_fen=rebate_amount_fen,
            source_channel_code_snapshot=direct_channel.channel_code,
            statement_month=_statement_month_now(),
            note=f"订单支付返佣:{order.order_no}:L{int(target_channel.level or 1)}",
        )
        db.add(ledger)
        db.flush()
        if created is None:
            created = ledger
    return created


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
    accrual_rows = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == order.order_no,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .order_by(desc(PartnerRebateLedger.id))
        .all()
    )
    return _create_missing_reversal_rows(
        db,
        accrual_rows=accrual_rows,
        statement_month=_statement_month_now(),
        note_prefix=f"订单退款冲正:{order.order_no}" + (f" [{operator}]" if operator else ""),
    )


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
    locked_channel = db.query(PartnerChannel).filter(PartnerChannel.id == int(channel.id)).with_for_update().first()
    if locked_channel is None:
        raise BizError(code=4476, message="渠道不存在")
    pending_request = (
        db.query(PartnerWithdrawRequest)
        .filter(
            PartnerWithdrawRequest.channel_id == int(locked_channel.id),
            PartnerWithdrawRequest.status.in_([PartnerWithdrawStatus.PENDING, PartnerWithdrawStatus.APPROVED]),
        )
        .with_for_update()
        .first()
    )
    if pending_request is not None:
        raise BizError(code=4497, message="当前存在未完成的提现申请，请先处理后再提交")
    summary = compute_partner_withdrawable_fen(db, channel_id=int(locked_channel.id))
    if normalized_amount > int(summary["withdrawable_fen"]):
        raise BizError(code=4472, message="可提现余额不足")
    request_no = f"WD{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3).upper()}"
    row = PartnerWithdrawRequest(
        request_no=request_no,
        channel_id=int(locked_channel.id),
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
    if month_key >= _statement_month_now():
        raise BizError(code=4470, message="仅允许为已结束的历史月份生成结算单")
    row = (
        db.query(PartnerMonthlyStatement)
        .filter(
            PartnerMonthlyStatement.channel_id == channel_id,
            PartnerMonthlyStatement.statement_month == month_key,
        )
        .with_for_update()
        .first()
    )
    pending_rows = (
        db.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.channel_id == channel_id,
            PartnerRebateLedger.statement_month == month_key,
            PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
            PartnerRebateLedger.entry_type.in_([PartnerLedgerEntryType.ACCRUAL, PartnerLedgerEntryType.REVERSAL]),
            or_(PartnerRebateLedger.statement_id.is_(None), PartnerRebateLedger.statement_id == (row.id if row is not None else None)),
        )
        .all()
    )
    if not pending_rows:
        if row is not None:
            return row, False
        raise BizError(code=4469, message="当前月份暂无待结算返佣流水")
    accrual_rows = [item for item in pending_rows if item.entry_type == PartnerLedgerEntryType.ACCRUAL]
    if row is not None:
        if row.status == PartnerStatementStatus.SETTLED:
            unassigned_rows = [item for item in pending_rows if item.statement_id is None]
            if unassigned_rows:
                raise BizError(code=4471, message="该结算月已结清，存在新的未归档流水，请人工复核")
            return row, False
        for item in pending_rows:
            item.statement_id = row.id
        row.total_orders = len({str(item.order_no or "") for item in accrual_rows if item.order_no})
        row.gross_amount_fen = sum(int(item.base_amount_fen or 0) for item in accrual_rows)
        row.rebate_amount_fen = sum(int(item.rebate_amount_fen or 0) for item in pending_rows)
        db.flush()
        return row, False
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


def authenticate_partner_portal_login(db: Session, *, account: str, password: str) -> PartnerChannel:
    normalized_account = _normalize_channel_code(account)
    plain_password = str(password or "")
    if not normalized_account or not plain_password:
        raise BizError(code=4479, message="渠道账号或密码不能为空")
    channel = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.channel_code == normalized_account)
        .with_for_update()
        .first()
    )
    if channel is None or str(channel.status or "").strip().lower() != "active":
        raise BizError(code=4480, message="渠道账号不存在或已停用", http_status=403)
    password_hash = str(channel.portal_password_hash or "").strip()
    if not password_hash:
        raise BizError(code=4481, message="该渠道尚未初始化门户密码，请联系平台管理员重置", http_status=403)
    if not verify_password(plain_password, password_hash):
        raise BizError(code=4482, message="渠道账号或密码错误", http_status=403)
    channel.portal_last_login_at = datetime.utcnow()
    db.flush()
    return channel


def reset_partner_portal_password(
    db: Session,
    *,
    channel: PartnerChannel,
    plain_password: str | None = None,
) -> tuple[PartnerChannel, str]:
    password = str(plain_password or "").strip() or generate_partner_portal_password()
    if len(password) < 8:
        raise BizError(code=4483, message="渠道门户密码长度至少 8 位")
    channel.portal_password_hash = hash_password(password)
    now = datetime.utcnow()
    channel.portal_password_updated_at = now
    db.flush()
    return channel, password


def change_partner_portal_password(
    db: Session,
    *,
    channel: PartnerChannel,
    old_password: str,
    new_password: str,
) -> PartnerChannel:
    old_text = str(old_password or "")
    new_text = str(new_password or "").strip()
    password_hash = str(channel.portal_password_hash or "").strip()
    if not password_hash:
        raise BizError(code=4491, message="该渠道尚未初始化密码，请先联系平台重置")
    if not old_text:
        raise BizError(code=4492, message="原密码不能为空")
    if not verify_password(old_text, password_hash):
        raise BizError(code=4493, message="原密码不正确", http_status=403)
    if len(new_text) < 8:
        raise BizError(code=4494, message="新密码长度至少 8 位")
    if new_text == old_text:
        raise BizError(code=4495, message="新密码不能与原密码相同")
    channel.portal_password_hash = hash_password(new_text)
    channel.portal_password_updated_at = datetime.utcnow()
    db.flush()
    return channel


def rotate_partner_portal_session(db: Session, *, channel: PartnerChannel) -> PartnerChannel:
    locked_channel = db.query(PartnerChannel).filter(PartnerChannel.id == int(channel.id)).with_for_update().first()
    if locked_channel is None:
        raise BizError(code=4476, message="渠道不存在")
    locked_channel.updated_at = datetime.utcnow()
    db.flush()
    return locked_channel


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
    child_count = (
        db.query(func.count(PartnerChannel.id))
        .filter(PartnerChannel.parent_channel_id == channel.id)
        .scalar()
        or 0
    )
    user_count = (
        db.query(func.count(PartnerUserBinding.id))
        .filter(PartnerUserBinding.channel_id == channel.id)
        .scalar()
        or 0
    )
    withdraw_summary = compute_partner_withdrawable_fen(db, channel_id=channel.id)
    return {
        "channel_id": channel.id,
        "channel_code": channel.channel_code,
        "channel_name": channel.name,
        "default_rebate_rate_bp": int(channel.default_rebate_rate_bp or 0),
        "default_rebate_rate_pct": round(float(int(channel.default_rebate_rate_bp or 0)) / 100.0, 2),
        "child_count": int(child_count),
        "user_count": int(user_count),
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
