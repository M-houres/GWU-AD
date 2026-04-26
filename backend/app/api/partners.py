from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from sqlalchemy import case, desc, func, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import current_partner, db_dep, get_redis, optional_partner, require_admin_permission
from app.exceptions import BizError
from app.models import (
    AdminUser,
    Order,
    PartnerChannel,
    PartnerLedgerEntryType,
    PartnerLedgerStatus,
    PartnerMonthlyStatement,
    PartnerOrderAttribution,
    PartnerPolicy,
    PartnerRebateLedger,
    PartnerUserBinding,
    PartnerWithdrawRequest,
    PartnerWithdrawStatus,
    User,
)
from app.money import cny_to_api, fen_to_cny
from app.pagination import paginate
from app.responses import ok
from app.schemas import APIResp
from app.security import auth_session_key, create_access_token, create_refresh_token, decode_token, new_session_version
from app.services.partner_rebate_service import (
    authenticate_partner_portal,
    authenticate_partner_portal_login,
    build_channel_links,
    change_partner_portal_password,
    compute_partner_withdrawable_fen,
    create_partner_channel,
    create_partner_withdraw_request,
    generate_monthly_statement,
    get_partner_portal_overview,
    mark_partner_withdraw_paid,
    reset_partner_portal_password,
    rotate_partner_portal_token,
    review_partner_withdraw_request,
    settle_monthly_statement,
    update_partner_channel,
    upsert_partner_policy,
)

router = APIRouter()
settings = get_settings()
PARTNER_ACCESS_COOKIE_NAME = "gw_partner_access"
PARTNER_REFRESH_COOKIE_NAME = "gw_partner_refresh"
ANALYTICS_TZ = timezone(timedelta(hours=8))
ANALYTICS_CACHE_TTL_SECONDS = 20


def _cookie_samesite() -> str:
    value = str(getattr(settings, "auth_cookie_samesite", "lax") or "lax").strip().lower()
    if value in {"none", "lax", "strict"}:
        return value
    return "lax"


def _apply_partner_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key=PARTNER_ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.jwt_expire_minutes) * 60,
        path="/",
    )
    response.set_cookie(
        key=PARTNER_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure_enabled,
        samesite=_cookie_samesite(),
        max_age=int(settings.refresh_token_expire_days) * 24 * 3600,
        path="/api/v1/partners/portal/auth",
    )


def _clear_partner_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=PARTNER_ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=PARTNER_REFRESH_COOKIE_NAME, path="/api/v1/partners/portal/auth")


def _store_partner_session(auth_store, *, channel_id: int, session_version: str) -> None:
    ttl = int(settings.refresh_token_expire_days) * 24 * 3600
    auth_store.setex(auth_session_key("partner", str(channel_id)), ttl, session_version)


def _clear_partner_session(auth_store, *, channel_id: int) -> None:
    auth_store.delete(auth_session_key("partner", str(channel_id)))


def _issue_partner_auth(auth_store, response: Response | None, channel: PartnerChannel) -> tuple[str, str]:
    session_version = new_session_version()
    _store_partner_session(auth_store, channel_id=int(channel.id), session_version=session_version)
    access_token = create_access_token(subject=str(channel.id), scope="partner", session_version=session_version)
    refresh_token = create_refresh_token(subject=str(channel.id), scope="partner", session_version=session_version)
    if response is not None:
        _apply_partner_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return access_token, refresh_token


def _fen_to_cny_api(value_fen: int) -> float:
    return cny_to_api(fen_to_cny(int(value_fen or 0)) or 0)


def _cny_to_fen_int(value) -> int:
    amount = cny_to_api(value)
    return int(round(float(amount) * 100))


def _channel_snapshot_map(db: Session, channel_ids: list[int]) -> dict[int, PartnerChannel]:
    unique_ids = sorted({int(item) for item in channel_ids if int(item or 0) > 0})
    if not unique_ids:
        return {}
    rows = db.query(PartnerChannel).filter(PartnerChannel.id.in_(unique_ids)).all()
    return {int(row.id): row for row in rows}


def _mask_phone(value: str | None) -> str:
    raw = str(value or "").strip()
    if len(raw) < 7:
      return raw
    return f"{raw[:3]}****{raw[-4:]}"


def _normalize_scope(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"direct", "subtree", "team"}:
        return normalized
    return "self"


def _direct_child_channel_ids(db: Session, *, channel_id: int) -> list[int]:
    rows = db.query(PartnerChannel.id).filter(PartnerChannel.parent_channel_id == int(channel_id)).all()
    return [int(row[0]) for row in rows if int(row[0] or 0) > 0]


def _scope_channel_ids(db: Session, *, channel: PartnerChannel, scope: str) -> list[int]:
    normalized_scope = _normalize_scope(scope)
    self_id = int(channel.id)
    direct_ids = _direct_child_channel_ids(db, channel_id=self_id)
    if normalized_scope == "direct":
        return direct_ids
    if normalized_scope == "subtree":
        return sorted({item for item in [self_id, *direct_ids] if int(item or 0) > 0})
    if normalized_scope == "team":
        return sorted({item for item in direct_ids if int(item or 0) > 0})
    return [self_id]


def _channel_tree_payload(db: Session, *, channel: PartnerChannel, request: Request | None = None) -> dict:
    payload = _channel_item_payload(db, channel, request=request)
    payload["self_summary"] = _team_summary_payload(db, channel_ids=[int(channel.id)], scope="self")
    payload["team_summary"] = _team_summary_payload(
        db,
        channel_ids=_scope_channel_ids(db, channel=channel, scope="team"),
        scope="team",
    )
    payload["subtree_summary"] = _team_summary_payload(
        db,
        channel_ids=_scope_channel_ids(db, channel=channel, scope="subtree"),
        scope="subtree",
    )
    children = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.parent_channel_id == int(channel.id))
        .order_by(PartnerChannel.id.asc())
        .all()
    )
    payload["children"] = [_channel_tree_payload(db, channel=row, request=request) for row in children]
    return payload


def _team_summary_payload(db: Session, *, channel_ids: list[int], scope: str) -> dict:
    normalized_ids = sorted({int(item) for item in channel_ids if int(item or 0) > 0})
    if not normalized_ids:
        return {
            "scope": _normalize_scope(scope),
            "channel_count": 0,
            "user_count": 0,
            "order_count": 0,
            "gross_amount_fen": 0,
            "gross_amount_cny": 0,
            "pending_rebate_fen": 0,
            "pending_rebate_cny": 0,
            "settled_rebate_fen": 0,
            "settled_rebate_cny": 0,
        }
    channel_count = db.query(func.count(PartnerChannel.id)).filter(PartnerChannel.id.in_(normalized_ids)).scalar() or 0
    user_count = db.query(func.count(PartnerUserBinding.id)).filter(PartnerUserBinding.channel_id.in_(normalized_ids)).scalar() or 0
    order_count = db.query(func.count(PartnerOrderAttribution.id)).filter(PartnerOrderAttribution.channel_id.in_(normalized_ids)).scalar() or 0
    gross_amount_cny = (
        db.query(func.coalesce(func.sum(Order.amount_cny), 0))
        .join(PartnerOrderAttribution, PartnerOrderAttribution.order_id == Order.id)
        .filter(PartnerOrderAttribution.channel_id.in_(normalized_ids))
        .scalar()
        or 0
    )
    pending_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id.in_(normalized_ids),
            PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
        )
        .scalar()
        or 0
    )
    settled_rebate_fen = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id.in_(normalized_ids),
            PartnerRebateLedger.status == PartnerLedgerStatus.SETTLED,
        )
        .scalar()
        or 0
    )
    gross_amount_fen = _cny_to_fen_int(gross_amount_cny)
    return {
        "scope": _normalize_scope(scope),
        "channel_count": int(channel_count),
        "user_count": int(user_count),
        "order_count": int(order_count),
        "gross_amount_fen": int(gross_amount_fen),
        "gross_amount_cny": _fen_to_cny_api(gross_amount_fen),
        "pending_rebate_fen": int(pending_rebate_fen),
        "pending_rebate_cny": _fen_to_cny_api(pending_rebate_fen),
        "settled_rebate_fen": int(settled_rebate_fen),
        "settled_rebate_cny": _fen_to_cny_api(settled_rebate_fen),
    }


def _normalize_analytics_days(days: int) -> int:
    return max(1, min(int(days or 14), 60))


def _analytics_now_local() -> datetime:
    return datetime.now(ANALYTICS_TZ)


def _analytics_window_start_utc(days: int) -> datetime:
    total_days = _normalize_analytics_days(days)
    start_date = _analytics_now_local().date() - timedelta(days=total_days - 1)
    start_local = datetime.combine(start_date, time.min, tzinfo=ANALYTICS_TZ)
    return start_local.astimezone(timezone.utc).replace(tzinfo=None)


def _date_bucket_keys(days: int) -> list[str]:
    total_days = _normalize_analytics_days(days)
    start_date = _analytics_now_local().date() - timedelta(days=total_days - 1)
    return [(start_date + timedelta(days=index)).isoformat() for index in range(total_days)]


def _serialize_date_key(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        current = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return current.astimezone(ANALYTICS_TZ).date().isoformat()
    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value)[:10]


def _analytics_date_bucket_expr(db: Session, column):
    dialect_name = str(getattr(getattr(db, "bind", None), "dialect", None).name or "").lower() if getattr(db, "bind", None) else ""
    if dialect_name.startswith("sqlite"):
        return func.date(column, "+8 hours")
    return func.date(func.timestampadd(text("HOUR"), 8, column))


def _analytics_cache_key(scope: str, **params) -> str:
    normalized = {key: params[key] for key in sorted(params)}
    return f"partners:analytics:{scope}:{json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"


def _analytics_cache_get(redis_client, key: str):
    try:
        cached = str(redis_client.get(key) or "").strip()
        if not cached:
            return None
        return json.loads(cached)
    except Exception:
        return None


def _analytics_cache_set(redis_client, key: str, data) -> None:
    try:
        redis_client.setex(key, ANALYTICS_CACHE_TTL_SECONDS, json.dumps(data, ensure_ascii=False, default=str))
    except Exception:
        return None


def _apply_admin_channel_filters(base_query, *, status: str | None = None, keyword: str | None = None):
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"active", "disabled"}:
        base_query = base_query.filter(PartnerChannel.status == normalized_status)
    normalized_keyword = str(keyword or "").strip()
    if normalized_keyword:
        like = f"%{normalized_keyword}%"
        base_query = base_query.filter((PartnerChannel.channel_code.like(like)) | (PartnerChannel.name.like(like)))
    return base_query


def _admin_partner_analytics_payload(
    db: Session,
    *,
    days: int = 14,
    status: str | None = None,
    keyword: str | None = None,
) -> dict:
    bucket_keys = _date_bucket_keys(days)
    growth_map = {key: {"date": key, "level_one_new": 0, "level_two_new": 0} for key in bucket_keys}
    start_dt = _analytics_window_start_utc(days)
    growth_bucket = _analytics_date_bucket_expr(db, PartnerChannel.created_at)
    growth_rows = (
        _apply_admin_channel_filters(
            db.query(growth_bucket.label("bucket_date"), PartnerChannel.level, func.count(PartnerChannel.id)),
            status=status,
            keyword=keyword,
        )
        .filter(PartnerChannel.created_at >= start_dt, PartnerChannel.level.in_([1, 2]))
        .group_by(growth_bucket, PartnerChannel.level)
        .all()
    )
    channels = _apply_admin_channel_filters(db.query(PartnerChannel), status=status, keyword=keyword).all()
    channel_ids = [int(row.id) for row in channels if int(row.id or 0) > 0]
    root_ids = [int(row.id) for row in channels if int(row.id or 0) > 0 and int(row.level or 1) == 1]

    for raw_date, raw_level, raw_count in growth_rows:
        key = _serialize_date_key(raw_date)
        bucket = growth_map.get(key)
        if bucket is None:
            continue
        level = int(raw_level or 1)
        if level == 1:
            bucket["level_one_new"] = int(raw_count or 0)
        elif level == 2:
            bucket["level_two_new"] = int(raw_count or 0)

    child_count_query = db.query(PartnerChannel.parent_channel_id, func.count(PartnerChannel.id)).filter(
        PartnerChannel.parent_channel_id.in_(root_ids or [0])
    )
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"active", "disabled"}:
        child_count_query = child_count_query.filter(PartnerChannel.status == normalized_status)
    child_counts = {
        int(row[0]): int(row[1] or 0)
        for row in child_count_query.group_by(PartnerChannel.parent_channel_id).all()
        if int(row[0] or 0) > 0
    }
    user_counts = {
        int(row[0]): int(row[1] or 0)
        for row in (
            db.query(PartnerUserBinding.channel_id, func.count(PartnerUserBinding.id))
            .filter(PartnerUserBinding.channel_id.in_(channel_ids or [0]))
            .group_by(PartnerUserBinding.channel_id)
            .all()
        )
        if int(row[0] or 0) > 0
    }
    pending_map: dict[int, int] = {}
    settled_map: dict[int, int] = {}
    rebate_rows = (
        db.query(
            PartnerRebateLedger.channel_id,
            func.coalesce(func.sum(case((PartnerRebateLedger.status == PartnerLedgerStatus.PENDING, PartnerRebateLedger.rebate_amount_fen), else_=0)), 0),
            func.coalesce(func.sum(case((PartnerRebateLedger.status == PartnerLedgerStatus.SETTLED, PartnerRebateLedger.rebate_amount_fen), else_=0)), 0),
        )
        .filter(PartnerRebateLedger.channel_id.in_(channel_ids or [0]))
        .group_by(PartnerRebateLedger.channel_id)
        .all()
    )
    for raw_channel_id, pending_amount, settled_amount in rebate_rows:
        channel_id = int(raw_channel_id or 0)
        if channel_id <= 0:
            continue
        pending_map[channel_id] = int(pending_amount or 0)
        settled_map[channel_id] = int(settled_amount or 0)

    customer_mix = []
    level_one_customer_count = sum(user_counts.get(int(item.id), 0) for item in channels if int(item.level or 1) == 1)
    level_two_customer_count = sum(user_counts.get(int(item.id), 0) for item in channels if int(item.level or 1) == 2)
    if level_one_customer_count > 0:
        customer_mix.append({"name": "一级归属", "value": int(level_one_customer_count)})
    if level_two_customer_count > 0:
        customer_mix.append({"name": "二级归属", "value": int(level_two_customer_count)})

    root_rank = [
        {
            "channel_id": channel_id,
            "name": str(row.name or "").strip() or f"渠道{channel_id}",
            "total_rebate_fen": int(pending_map.get(channel_id, 0) + settled_map.get(channel_id, 0)),
        }
        for row in channels
        for channel_id in [int(row.id or 0)]
        if channel_id in root_ids
    ]
    root_rank.sort(key=lambda item: (item["total_rebate_fen"], -item["channel_id"]), reverse=True)
    root_rank = root_rank[:8]

    anomalies = []
    now_ts = datetime.utcnow()
    for channel in channels:
        channel_id = int(channel.id or 0)
        level = int(channel.level or 1)
        status = str(channel.status or "")
        user_count = int(user_counts.get(channel_id, 0))
        child_count = int(child_counts.get(channel_id, 0))
        pending_fen = int(pending_map.get(channel_id, 0))
        stale_days = None
        if channel.portal_last_login_at:
            stale_days = int((now_ts - channel.portal_last_login_at).days)

        if level == 1 and child_count == 0:
            anomalies.append(
                {
                    "channel_id": channel_id,
                    "title": f"{channel.name} 还没有二级",
                    "desc": "一级渠道已建，但还没有开始发展二级渠道。",
                    "severity": "warning",
                    "level": "待扩张",
                    "type": "no-child",
                }
            )
        if level == 2 and user_count == 0 and pending_fen <= 0:
            anomalies.append(
                {
                    "channel_id": channel_id,
                    "title": f"{channel.name} 暂未起量",
                    "desc": "当前没有客户沉淀，也没有返佣数据。",
                    "severity": "danger",
                    "level": "待激活",
                    "type": "idle-second",
                }
            )
        if status == "disabled" and user_count > 0:
            anomalies.append(
                {
                    "channel_id": channel_id,
                    "title": f"{channel.name} 已停用但仍有客户归属",
                    "desc": "建议确认停用原因，避免客户归属长期挂起。",
                    "severity": "danger",
                    "level": "异常",
                    "type": "disabled-with-users",
                }
            )
        if pending_fen >= 50000:
            anomalies.append(
                {
                    "channel_id": channel_id,
                    "title": f"{channel.name} 待结算返佣偏高",
                    "desc": f"当前待结算 {_fen_to_cny_api(pending_fen):.2f} 元，建议尽快处理月结或提现审核。",
                    "severity": "warning",
                    "level": "待处理",
                    "type": "high-pending",
                }
            )
        if stale_days is not None and stale_days >= 14 and status == "active":
            anomalies.append(
                {
                    "channel_id": channel_id,
                    "title": f"{channel.name} 近 {stale_days} 天未登录",
                    "desc": "建议跟进渠道负责人，确认门户是否在持续使用。",
                    "severity": "muted",
                    "level": "待跟进",
                    "type": "stale-login",
                }
            )

    anomalies.sort(key=lambda item: ({"danger": 0, "warning": 1, "muted": 2}.get(item["severity"], 3), item["channel_id"]))

    total_pending_fen = sum(pending_map.values())
    total_settled_fen = sum(settled_map.values())
    pending_withdrawal_count = (
        db.query(func.count(PartnerWithdrawRequest.id))
        .filter(
            PartnerWithdrawRequest.channel_id.in_(channel_ids or [0]),
            PartnerWithdrawRequest.status == PartnerWithdrawStatus.PENDING,
        )
        .scalar()
        or 0
    )

    return {
        "summary": {
            "root_channel_count": len(root_ids),
            "active_second_count": len([item for item in channels if int(item.level or 1) == 2 and str(item.status or "") == "active"]),
            "pending_withdrawal_count": int(pending_withdrawal_count),
            "total_pending_rebate_fen": int(total_pending_fen),
            "total_rebate_pool_fen": int(total_pending_fen + int(total_settled_fen or 0)),
        },
        "growth_series": [growth_map[key] for key in bucket_keys],
        "root_rank": root_rank,
        "customer_mix": customer_mix,
        "anomalies": anomalies[:8],
    }


def _portal_partner_analytics_payload(
    db: Session,
    *,
    channel: PartnerChannel,
    days: int = 14,
    scope: str = "self",
) -> dict:
    bucket_keys = _date_bucket_keys(days)
    resolved_scope = "self" if int(channel.level or 1) != 1 else _normalize_scope(scope or "subtree")
    channel_ids = _scope_channel_ids(db, channel=channel, scope=resolved_scope)
    start_dt = _analytics_window_start_utc(days)
    customer_bucket = _analytics_date_bucket_expr(db, PartnerUserBinding.created_at)
    order_bucket = _analytics_date_bucket_expr(db, PartnerOrderAttribution.created_at)
    rebate_bucket = _analytics_date_bucket_expr(db, PartnerRebateLedger.created_at)
    trend_map = {
        key: {
            "date": key,
            "new_customers": 0,
            "order_count": 0,
            "rebate_amount_cny": 0.0,
        }
        for key in bucket_keys
    }

    customer_rows = (
        db.query(customer_bucket.label("bucket_date"), func.count(PartnerUserBinding.id))
        .filter(PartnerUserBinding.channel_id.in_(channel_ids or [0]), PartnerUserBinding.created_at >= start_dt)
        .group_by(customer_bucket)
        .all()
    )
    for raw_date, raw_count in customer_rows:
        key = _serialize_date_key(raw_date)
        if key in trend_map:
            trend_map[key]["new_customers"] = int(raw_count or 0)

    order_rows = (
        db.query(order_bucket.label("bucket_date"), func.count(PartnerOrderAttribution.id))
        .filter(PartnerOrderAttribution.channel_id.in_(channel_ids or [0]), PartnerOrderAttribution.created_at >= start_dt)
        .group_by(order_bucket)
        .all()
    )
    for raw_date, raw_count in order_rows:
        key = _serialize_date_key(raw_date)
        if key in trend_map:
            trend_map[key]["order_count"] = int(raw_count or 0)

    rebate_rows = (
        db.query(rebate_bucket.label("bucket_date"), func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id.in_(channel_ids or [0]),
            PartnerRebateLedger.created_at >= start_dt,
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .group_by(rebate_bucket)
        .all()
    )
    for raw_date, raw_amount in rebate_rows:
        key = _serialize_date_key(raw_date)
        if key in trend_map:
            trend_map[key]["rebate_amount_cny"] = round(float(int(raw_amount or 0)) / 100.0, 2)

    subchannel_rank = []
    package_mix = []
    child_summary = {
        "child_count": 0,
        "idle_child_count": 0,
        "active_child_count": 0,
        "total_rebate_fen": 0,
    }
    if int(channel.level or 1) == 1:
        direct_rows = (
            db.query(PartnerChannel)
            .filter(PartnerChannel.parent_channel_id == int(channel.id))
            .order_by(PartnerChannel.id.asc())
            .all()
        )
        direct_ids = [int(row.id) for row in direct_rows]
        user_map = {
            int(row[0]): int(row[1] or 0)
            for row in (
                db.query(PartnerUserBinding.channel_id, func.count(PartnerUserBinding.id))
                .filter(PartnerUserBinding.channel_id.in_(direct_ids or [0]))
                .group_by(PartnerUserBinding.channel_id)
                .all()
            )
            if int(row[0] or 0) > 0
        }
        rebate_map = {
            int(row[0]): int(row[1] or 0)
            for row in (
                db.query(PartnerRebateLedger.channel_id, func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
                .filter(
                    PartnerRebateLedger.channel_id.in_(direct_ids or [0]),
                    PartnerRebateLedger.status.in_([PartnerLedgerStatus.PENDING, PartnerLedgerStatus.SETTLED]),
                )
                .group_by(PartnerRebateLedger.channel_id)
                .all()
            )
            if int(row[0] or 0) > 0
        }
        subchannel_rank = [
            {
                "channel_id": int(row.id),
                "name": str(row.name or "").strip() or f"渠道{row.id}",
                "user_count": int(user_map.get(int(row.id), 0)),
                "rebate_amount_fen": int(rebate_map.get(int(row.id), 0)),
            }
            for row in direct_rows
        ]
        subchannel_rank.sort(key=lambda item: (item["rebate_amount_fen"], item["user_count"]), reverse=True)
        child_summary = {
            "child_count": len(direct_rows),
            "idle_child_count": len([item for item in subchannel_rank if int(item["user_count"]) <= 0 and int(item["rebate_amount_fen"]) <= 0]),
            "active_child_count": len([item for item in direct_rows if str(item.status or "") == "active"]),
            "total_rebate_fen": int(sum(item["rebate_amount_fen"] for item in subchannel_rank)),
        }
    else:
        package_rows = (
            db.query(PartnerOrderAttribution.package_name, func.count(PartnerOrderAttribution.id))
            .filter(PartnerOrderAttribution.channel_id == int(channel.id))
            .group_by(PartnerOrderAttribution.package_name)
            .order_by(desc(func.count(PartnerOrderAttribution.id)))
            .limit(6)
            .all()
        )
        package_mix = [
            {
                "name": str(row[0] or "").strip() or "未区分套餐",
                "value": int(row[1] or 0),
            }
            for row in package_rows
        ]

    return {
        "level": int(channel.level or 1),
        "scope": resolved_scope,
        "trend_series": [trend_map[key] for key in bucket_keys],
        "subchannel_rank": subchannel_rank,
        "package_mix": package_mix,
        "child_summary": child_summary,
    }


def _customer_list_payload(
    db: Session,
    *,
    channel_ids: list[int],
    page: int,
    page_size: int,
    keyword: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> dict:
    normalized_ids = sorted({int(item) for item in channel_ids if int(item or 0) > 0})
    if not normalized_ids:
        return {"items": [], "pagination": paginate(0, page, page_size)}
    base_query = (
        db.query(PartnerUserBinding, User, PartnerChannel)
        .join(User, User.id == PartnerUserBinding.user_id)
        .join(PartnerChannel, PartnerChannel.id == PartnerUserBinding.channel_id)
        .filter(PartnerUserBinding.channel_id.in_(normalized_ids))
    )
    normalized_keyword = str(keyword or "").strip()
    if normalized_keyword:
        like = f"%{normalized_keyword}%"
        base_query = base_query.filter((User.nickname.like(like)) | (PartnerChannel.name.like(like)) | (PartnerChannel.channel_code.like(like)))
    created_from_dt = _parse_datetime_filter(created_from)
    if created_from_dt is not None:
        base_query = base_query.filter(PartnerUserBinding.created_at >= created_from_dt)
    created_to_dt = _parse_datetime_filter(created_to)
    if created_to_dt is not None:
        base_query = base_query.filter(PartnerUserBinding.created_at <= created_to_dt)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerUserBinding.updated_at), desc(PartnerUserBinding.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    user_ids = [int(user.id) for _, user, _ in rows if int(user.id or 0) > 0]
    attr_stats = (
        db.query(
            PartnerOrderAttribution.user_id,
            func.count(PartnerOrderAttribution.id),
            func.max(PartnerOrderAttribution.created_at),
        )
        .filter(PartnerOrderAttribution.user_id.in_(user_ids or [0]))
        .group_by(PartnerOrderAttribution.user_id)
        .all()
    )
    attr_map = {int(row[0]): {"order_count": int(row[1] or 0), "last_attributed_at": row[2]} for row in attr_stats}
    items = []
    for binding, user, channel in rows:
        stat = attr_map.get(int(user.id), {})
        items.append(
            {
                "binding_id": int(binding.id),
                "user_id": int(user.id),
                "nickname": str(user.nickname or "").strip() or f"用户{user.id}",
                "phone_masked": _mask_phone(user.phone),
                "bind_source": str(binding.bind_source or ""),
                "channel_id": int(channel.id),
                "channel_name": str(channel.name or ""),
                "channel_code": str(channel.channel_code or ""),
                "locked_at": binding.locked_at,
                "order_count": int(stat.get("order_count", 0)),
                "last_attributed_at": stat.get("last_attributed_at"),
                "created_at": binding.created_at,
                "updated_at": binding.updated_at,
            }
        )
    return {"items": items, "pagination": paginate(total, page, page_size)}


def _normalize_datetime_filter(value: str | None) -> str:
    return str(value or "").strip()


def _parse_datetime_filter(value: str | None) -> datetime | None:
    raw = _normalize_datetime_filter(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _channel_item_payload(db: Session, channel: PartnerChannel, request: Request | None = None) -> dict:
    pending = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.status == PartnerLedgerStatus.PENDING,
        )
        .scalar()
        or 0
    )
    settled = (
        db.query(func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0))
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.status == PartnerLedgerStatus.SETTLED,
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
    parent = None
    if channel.parent_channel_id:
        parent = db.query(PartnerChannel).filter(PartnerChannel.id == channel.parent_channel_id).first()
    links = build_channel_links(channel, request=request)
    return {
        "id": channel.id,
        "channel_code": channel.channel_code,
        "parent_channel_id": channel.parent_channel_id,
        "parent_channel_name": parent.name if parent is not None else "",
        "root_channel_id": channel.root_channel_id or channel.id,
        "level": int(channel.level or 1),
        "name": channel.name,
        "contact_name": channel.contact_name,
        "contact_phone": channel.contact_phone,
        "status": channel.status,
        "default_rebate_rate_bp": int(channel.default_rebate_rate_bp or 0),
        "default_rebate_rate_pct": round(float(int(channel.default_rebate_rate_bp or 0)) / 100.0, 2),
        "child_count": int(child_count),
        "user_count": int(user_count),
        "order_token": channel.order_token,
        "portal_token": channel.portal_token,
        "portal_account": channel.channel_code,
        "portal_last_login_at": channel.portal_last_login_at,
        "order_link": links["order_link"],
        "portal_link": links["portal_link"],
        "portal_login_link": links["portal_login_link"],
        "miniapp_order_path": links["miniapp_order_path"],
        "miniapp_portal_path": links["miniapp_portal_path"],
        "pending_rebate_fen": int(pending),
        "pending_rebate_cny": _fen_to_cny_api(pending),
        "settled_rebate_fen": int(settled),
        "settled_rebate_cny": _fen_to_cny_api(settled),
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


def _channel_secret_payload(
    db: Session,
    channel: PartnerChannel,
    *,
    portal_password: str,
    request: Request | None = None,
) -> dict:
    data = _channel_item_payload(db, channel, request=request)
    data["portal_password"] = portal_password
    return data


def _withdraw_item_payload(row: PartnerWithdrawRequest, channel: PartnerChannel | None = None) -> dict:
    return {
        "id": row.id,
        "request_no": row.request_no,
        "channel_id": row.channel_id,
        "channel_name": channel.name if channel is not None else "",
        "channel_code": channel.channel_code if channel is not None else "",
        "apply_amount_fen": int(row.apply_amount_fen or 0),
        "apply_amount_cny": _fen_to_cny_api(row.apply_amount_fen),
        "status": row.status.value,
        "note": row.note,
        "reject_reason": row.reject_reason,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "paid_at": row.paid_at,
        "created_at": row.created_at,
    }


def _portal_managed_channel(
    current_channel: PartnerChannel,
    target_channel_id: int,
    db: Session,
    *,
    allow_self: bool = False,
) -> PartnerChannel:
    target = db.query(PartnerChannel).filter(PartnerChannel.id == int(target_channel_id)).with_for_update().first()
    if target is None:
        raise ValueError("渠道不存在")
    if allow_self and int(target.id) == int(current_channel.id):
        return target
    if int(target.parent_channel_id or 0) != int(current_channel.id):
        raise ValueError("仅可管理直属下级渠道")
    return target


@router.post("/admin/channels", response_model=APIResp)
def admin_create_partner_channel(
    request: Request,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if payload.get("parent_channel_id") not in {None, "", 0, "0"}:
        raise BizError(code=4481, message="平台后台仅创建一级渠道，下级渠道请由上级在渠道后台创建")
    channel = create_partner_channel(
        db,
        name=str(payload.get("name") or ""),
        contact_name=str(payload.get("contact_name") or ""),
        contact_phone=str(payload.get("contact_phone") or ""),
        channel_code=payload.get("channel_code"),
        rebate_rate_bp=payload.get("rebate_rate_bp", 1500),
        parent_channel_id=None,
    )
    channel, portal_password = reset_partner_portal_password(db, channel=channel)
    db.commit()
    db.refresh(channel)
    return ok(data=_channel_secret_payload(db, channel, portal_password=portal_password, request=request))


@router.get("/admin/channels", response_model=APIResp)
def admin_list_partner_channels(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = _apply_admin_channel_filters(db.query(PartnerChannel), status=status, keyword=keyword)
    total = base_query.count()
    rows = (
        base_query.order_by(PartnerChannel.level.asc(), desc(PartnerChannel.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        data={
            "items": [_channel_item_payload(db, row, request=request) for row in rows],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.get("/admin/channels/tree", response_model=APIResp)
def admin_partner_channel_tree(
    request: Request,
    root_channel_id: int | None = Query(default=None, ge=1),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    if root_channel_id:
        root = db.query(PartnerChannel).filter(PartnerChannel.id == int(root_channel_id)).first()
        if root is None:
            return ok(data={"items": []}, message="渠道不存在")
        return ok(data={"items": [_channel_tree_payload(db, channel=root, request=request)]})
    roots = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.parent_channel_id.is_(None))
        .order_by(PartnerChannel.id.asc())
        .all()
    )
    return ok(data={"items": [_channel_tree_payload(db, channel=row, request=request) for row in roots]})


@router.patch("/admin/channels/{channel_id}", response_model=APIResp)
def admin_update_partner_channel(
    channel_id: int,
    request: Request,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).with_for_update().first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    channel = update_partner_channel(
        db,
        channel=channel,
        name=payload.get("name") if "name" in payload else None,
        contact_name=payload.get("contact_name") if "contact_name" in payload else None,
        contact_phone=payload.get("contact_phone") if "contact_phone" in payload else None,
        status=payload.get("status") if "status" in payload else None,
        rebate_rate_bp=payload.get("rebate_rate_bp") if "rebate_rate_bp" in payload else None,
    )
    db.commit()
    db.refresh(channel)
    return ok(data=_channel_item_payload(db, channel, request=request))


@router.delete("/admin/channels/{channel_id}", response_model=APIResp)
def admin_delete_partner_channel(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).with_for_update().first()
    if channel is None:
        return ok(data=None, message="渠道不存在")

    confirm_name = str(payload.get("confirm_name") or "").strip()
    if confirm_name != str(channel.name or "").strip():
        raise BizError(code=4483, message="请输入正确的渠道名称后再删除")

    child_exists = db.query(PartnerChannel.id).filter(PartnerChannel.parent_channel_id == channel.id).first()
    if child_exists is not None:
        raise BizError(code=4484, message="该渠道还有直属下级，不能删除")

    binding_exists = db.query(PartnerUserBinding.id).filter(PartnerUserBinding.channel_id == channel.id).first()
    if binding_exists is not None:
        raise BizError(code=4485, message="该渠道已有客户归属，不能删除")

    attribution_exists = db.query(PartnerOrderAttribution.id).filter(PartnerOrderAttribution.channel_id == channel.id).first()
    if attribution_exists is not None:
        raise BizError(code=4486, message="该渠道已有订单归属记录，不能删除")

    ledger_exists = db.query(PartnerRebateLedger.id).filter(PartnerRebateLedger.channel_id == channel.id).first()
    if ledger_exists is not None:
        raise BizError(code=4487, message="该渠道已有返佣流水，不能删除")

    statement_exists = db.query(PartnerMonthlyStatement.id).filter(PartnerMonthlyStatement.channel_id == channel.id).first()
    if statement_exists is not None:
        raise BizError(code=4488, message="该渠道已有月结记录，不能删除")

    withdraw_exists = db.query(PartnerWithdrawRequest.id).filter(PartnerWithdrawRequest.channel_id == channel.id).first()
    if withdraw_exists is not None:
        raise BizError(code=4489, message="该渠道已有提现记录，不能删除")

    db.query(PartnerPolicy).filter(PartnerPolicy.channel_id == channel.id).delete(synchronize_session=False)
    db.delete(channel)
    _clear_partner_session(auth_store, channel_id=int(channel_id))
    db.commit()
    return ok(data=True, message="渠道已删除")


@router.post("/admin/channels/{channel_id}/children", response_model=APIResp)
def admin_create_partner_child_channel(
    channel_id: int,
    request: Request,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    raise BizError(code=4482, message="平台后台不直接创建下级，请由上级渠道在渠道后台创建直属下级")


@router.post("/admin/channels/{channel_id}/policy", response_model=APIResp)
def admin_upsert_partner_policy(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    row = upsert_partner_policy(
        db,
        channel_id=channel_id,
        package_name=payload.get("package_name"),
        rebate_rate_bp=payload.get("rebate_rate_bp", channel.default_rebate_rate_bp),
        is_active=bool(payload.get("is_active", True)),
    )
    db.commit()
    db.refresh(row)
    return ok(
        data={
            "id": row.id,
            "channel_id": row.channel_id,
            "package_name": row.package_name or "*",
            "rebate_rate_bp": int(row.rebate_rate_bp or 0),
            "rebate_rate_pct": round(float(int(row.rebate_rate_bp or 0)) / 100.0, 2),
            "is_active": bool(row.is_active),
            "updated_at": row.updated_at,
        }
    )


@router.get("/admin/channels/{channel_id}/policies", response_model=APIResp)
def admin_list_partner_policies(
    channel_id: int,
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    rows = (
        db.query(PartnerPolicy)
        .filter(PartnerPolicy.channel_id == channel_id)
        .order_by(desc(PartnerPolicy.id))
        .all()
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "channel_id": row.channel_id,
                    "package_name": row.package_name or "*",
                    "rebate_rate_bp": int(row.rebate_rate_bp or 0),
                    "rebate_rate_pct": round(float(int(row.rebate_rate_bp or 0)) / 100.0, 2),
                    "is_active": bool(row.is_active),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]
        }
    )


@router.get("/admin/channels/{channel_id}/team-summary", response_model=APIResp)
def admin_partner_team_summary(
    channel_id: int,
    scope: str | None = Query(default="subtree"),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    return ok(data=_team_summary_payload(db, channel_ids=channel_ids, scope=scope))


@router.get("/admin/channels/{channel_id}/customers", response_model=APIResp)
def admin_partner_customers(
    channel_id: int,
    scope: str | None = Query(default="subtree"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    return ok(
        data=_customer_list_payload(
            db,
            channel_ids=channel_ids,
            page=page,
            page_size=page_size,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.get("/admin/analytics", response_model=APIResp)
def admin_partner_analytics(
    days: int = Query(default=14, ge=7, le=60),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    cache_key = _analytics_cache_key("admin", days=int(days), status=str(status or "").strip().lower(), keyword=str(keyword or "").strip())
    cached = _analytics_cache_get(redis_client, cache_key)
    if cached is not None:
        return ok(data=cached)
    data = _admin_partner_analytics_payload(db, days=days, status=status, keyword=keyword)
    _analytics_cache_set(redis_client, cache_key, data)
    return ok(data=data)


@router.get("/admin/ledger", response_model=APIResp)
def admin_partner_rebate_ledger(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    channel_id: int | None = Query(default=None, ge=1),
    statement_month: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PartnerRebateLedger)
    if channel_id:
        base_query = base_query.filter(PartnerRebateLedger.channel_id == channel_id)
    normalized_month = str(statement_month or "").strip()
    if normalized_month:
        base_query = base_query.filter(PartnerRebateLedger.statement_month == normalized_month)
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"pending", "settled", "reversed"}:
        base_query = base_query.filter(PartnerRebateLedger.status == normalized_status)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerRebateLedger.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    channel_map = _channel_snapshot_map(
        db,
        [int(row.channel_id or 0) for row in rows] + [int(row.source_channel_id or 0) for row in rows],
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "channel_id": row.channel_id,
                    "channel_name": channel_map.get(int(row.channel_id or 0)).name if channel_map.get(int(row.channel_id or 0)) else "",
                    "channel_code": channel_map.get(int(row.channel_id or 0)).channel_code if channel_map.get(int(row.channel_id or 0)) else "",
                    "source_channel_id": row.source_channel_id,
                    "source_channel_name": channel_map.get(int(row.source_channel_id or 0)).name if channel_map.get(int(row.source_channel_id or 0)) else "",
                    "order_no": row.order_no,
                    "entry_type": row.entry_type.value,
                    "status": row.status.value,
                    "base_amount_fen": int(row.base_amount_fen or 0),
                    "base_amount_cny": _fen_to_cny_api(row.base_amount_fen),
                    "rebate_rate_bp": int(row.rebate_rate_bp or 0),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
                    "source_channel_code": row.source_channel_code_snapshot,
                    "statement_month": row.statement_month,
                    "statement_id": row.statement_id,
                    "note": row.note,
                    "created_at": row.created_at,
                    "settled_at": row.settled_at,
                }
                for row in rows
            ],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.post("/admin/statements/generate", response_model=APIResp)
def admin_generate_partner_statement(
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel_id = int(payload.get("channel_id") or 0)
    if channel_id <= 0:
        return ok(data=None, message="channel_id 无效")
    statement, created = generate_monthly_statement(
        db,
        channel_id=channel_id,
        statement_month=str(payload.get("statement_month") or "").strip(),
    )
    db.commit()
    db.refresh(statement)
    return ok(
        data={
            "id": statement.id,
            "channel_id": statement.channel_id,
            "statement_month": statement.statement_month,
            "status": statement.status.value,
            "total_orders": int(statement.total_orders or 0),
            "gross_amount_fen": int(statement.gross_amount_fen or 0),
            "gross_amount_cny": _fen_to_cny_api(statement.gross_amount_fen),
            "rebate_amount_fen": int(statement.rebate_amount_fen or 0),
            "rebate_amount_cny": _fen_to_cny_api(statement.rebate_amount_fen),
            "created": created,
            "created_at": statement.created_at,
        }
    )


@router.post("/admin/statements/{statement_id}/settle", response_model=APIResp)
def admin_settle_partner_statement(
    statement_id: int,
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    statement, idempotent = settle_monthly_statement(
        db,
        statement_id=statement_id,
        admin_id=admin.id,
    )
    db.commit()
    db.refresh(statement)
    return ok(
        data={
            "id": statement.id,
            "channel_id": statement.channel_id,
            "statement_month": statement.statement_month,
            "status": statement.status.value,
            "idempotent": bool(idempotent),
            "settled_by": statement.settled_by,
            "settled_at": statement.settled_at,
        }
    )


@router.get("/admin/statements", response_model=APIResp)
def admin_list_partner_statements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    channel_id: int | None = Query(default=None, ge=1),
    statement_month: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PartnerMonthlyStatement)
    if channel_id:
        base_query = base_query.filter(PartnerMonthlyStatement.channel_id == channel_id)
    normalized_month = str(statement_month or "").strip()
    if normalized_month:
        base_query = base_query.filter(PartnerMonthlyStatement.statement_month == normalized_month)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerMonthlyStatement.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "channel_id": row.channel_id,
                    "statement_month": row.statement_month,
                    "status": row.status.value,
                    "total_orders": int(row.total_orders or 0),
                    "gross_amount_fen": int(row.gross_amount_fen or 0),
                    "gross_amount_cny": _fen_to_cny_api(row.gross_amount_fen),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
                    "settled_by": row.settled_by,
                    "settled_at": row.settled_at,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.get("/admin/withdrawals", response_model=APIResp)
def admin_list_partner_withdrawals(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    channel_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PartnerWithdrawRequest)
    if channel_id:
        base_query = base_query.filter(PartnerWithdrawRequest.channel_id == channel_id)
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"pending", "approved", "rejected", "paid"}:
        base_query = base_query.filter(PartnerWithdrawRequest.status == normalized_status)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerWithdrawRequest.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    channel_map = _channel_snapshot_map(db, [int(row.channel_id or 0) for row in rows])
    return ok(
        data={
            "items": [_withdraw_item_payload(row, channel_map.get(int(row.channel_id or 0))) for row in rows],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.post("/admin/withdrawals/{request_id}/review", response_model=APIResp)
def admin_review_partner_withdraw(
    request_id: int,
    payload: dict = Body(default_factory=dict),
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    approve = bool(payload.get("approve", False))
    row = review_partner_withdraw_request(
        db,
        request_id=request_id,
        admin_id=admin.id,
        approve=approve,
        reject_reason=str(payload.get("reject_reason") or ""),
    )
    db.commit()
    db.refresh(row)
    return ok(data=_withdraw_item_payload(row))


@router.post("/admin/withdrawals/{request_id}/mark-paid", response_model=APIResp)
def admin_mark_partner_withdraw_paid(
    request_id: int,
    admin: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = mark_partner_withdraw_paid(db, request_id=request_id, admin_id=admin.id)
    db.commit()
    db.refresh(row)
    return ok(data=_withdraw_item_payload(row))


def _portal_channel(
    db: Session,
    current_channel: PartnerChannel | None = None,
    channel_code: str | None = None,
    portal_token: str | None = None,
) -> PartnerChannel:
    if current_channel is not None:
        return current_channel
    normalized_code = str(channel_code or "").strip()
    normalized_token = str(portal_token or "").strip()
    if normalized_code and normalized_token:
        return authenticate_partner_portal(
            db,
            channel_code=normalized_code,
            portal_token=normalized_token,
        )
    raise BizError(code=4486, message="渠道登录态已失效，请重新登录", http_status=401)


def _partner_auth_payload(channel: PartnerChannel) -> dict:
    return {
        "channel": {
            "id": int(channel.id),
            "channel_code": str(channel.channel_code or ""),
            "name": str(channel.name or ""),
            "level": int(channel.level or 1),
            "status": str(channel.status or ""),
            "contact_name": str(channel.contact_name or ""),
            "contact_phone": str(channel.contact_phone or ""),
            "portal_last_login_at": channel.portal_last_login_at,
        }
    }


@router.post("/portal/auth/login", response_model=APIResp)
def partner_portal_login(
    response: Response,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = authenticate_partner_portal_login(
        db,
        account=str(payload.get("account") or payload.get("channel_code") or ""),
        password=str(payload.get("password") or ""),
    )
    access_token, refresh_token = _issue_partner_auth(auth_store, response, channel)
    db.commit()
    db.refresh(channel)
    data = _partner_auth_payload(channel)
    data["token"] = access_token
    data["refresh_token"] = refresh_token
    return ok(data=data)


@router.post("/portal/auth/exchange", response_model=APIResp)
def partner_portal_exchange(
    response: Response,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = authenticate_partner_portal(
        db,
        channel_code=str(payload.get("channel_code") or payload.get("ch") or ""),
        portal_token=str(payload.get("portal_token") or payload.get("pk") or ""),
    )
    channel.portal_last_login_at = datetime.utcnow()
    access_token, refresh_token = _issue_partner_auth(auth_store, response, channel)
    db.commit()
    db.refresh(channel)
    data = _partner_auth_payload(channel)
    data["token"] = access_token
    data["refresh_token"] = refresh_token
    return ok(data=data)


@router.post("/portal/auth/refresh", response_model=APIResp)
def partner_portal_refresh(
    response: Response,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise BizError(code=4484, message="缺少刷新凭证", http_status=401)
    try:
        decoded = decode_token(refresh_token)
    except ValueError as exc:
        raise BizError(code=4485, message="刷新凭证无效", http_status=401) from exc
    if decoded.get("scope") != "partner" or str(decoded.get("typ") or "").strip().lower() != "refresh":
        raise BizError(code=4485, message="刷新凭证无效", http_status=401)
    channel_id = int(decoded.get("sub") or 0)
    if channel_id <= 0:
        raise BizError(code=4485, message="刷新凭证无效", http_status=401)
    session_version = str(decoded.get("sv") or "").strip()
    current_session = str(auth_store.get(auth_session_key("partner", str(channel_id))) or "").strip()
    if not session_version or not current_session or session_version != current_session:
        raise BizError(code=4486, message="渠道登录态已失效，请重新登录", http_status=401)
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).first()
    if channel is None or str(channel.status or "").strip().lower() != "active":
        raise BizError(code=4487, message="渠道账号不存在或已停用", http_status=403)
    access_token, next_refresh_token = _issue_partner_auth(auth_store, response, channel)
    db.commit()
    db.refresh(channel)
    data = _partner_auth_payload(channel)
    data["token"] = access_token
    data["refresh_token"] = next_refresh_token
    return ok(data=data)


@router.post("/portal/auth/logout", response_model=APIResp)
def partner_portal_logout(
    response: Response,
    current_channel: PartnerChannel | None = Depends(optional_partner),
    auth_store=Depends(get_redis),
) -> APIResp:
    if current_channel is not None:
        _clear_partner_session(auth_store, channel_id=int(current_channel.id))
    _clear_partner_auth_cookies(response)
    return ok(data=True)


@router.post("/portal/auth/change-password", response_model=APIResp)
def partner_portal_change_password(
    payload: dict = Body(default_factory=dict),
    current_channel: PartnerChannel = Depends(current_partner),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = change_partner_portal_password(
        db,
        channel=current_channel,
        old_password=str(payload.get("old_password") or ""),
        new_password=str(payload.get("new_password") or ""),
    )
    db.commit()
    db.refresh(channel)
    return ok(data=_partner_auth_payload(channel), message="密码已更新")


@router.get("/portal/overview", response_model=APIResp)
def portal_overview(
    request: Request,
    statement_month: str | None = Query(default=None),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    overview = get_partner_portal_overview(db, channel=channel, statement_month=statement_month)
    parent = None
    if channel.parent_channel_id:
        parent = db.query(PartnerChannel).filter(PartnerChannel.id == channel.parent_channel_id).first()
    links = build_channel_links(channel, request=request)
    overview["level"] = int(channel.level or 1)
    overview["parent_channel_id"] = channel.parent_channel_id
    overview["parent_channel_name"] = str(parent.name or "") if parent is not None else ""
    overview["can_create_child"] = int(channel.level or 1) < 2
    overview.update(links)
    overview["team_direct"] = _team_summary_payload(
        db,
        channel_ids=_scope_channel_ids(db, channel=channel, scope="direct"),
        scope="direct",
    )
    overview["team_subtree"] = _team_summary_payload(
        db,
        channel_ids=_scope_channel_ids(db, channel=channel, scope="subtree"),
        scope="subtree",
    )
    return ok(data=overview)


@router.get("/portal/orders", response_model=APIResp)
def portal_orders(
    request: Request,
    scope: str | None = Query(default="self"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    base_query = (
        db.query(PartnerRebateLedger, Order)
        .join(Order, Order.id == PartnerRebateLedger.order_id)
        .filter(
            PartnerRebateLedger.channel_id.in_(channel_ids),
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
            PartnerRebateLedger.order_id.is_not(None),
        )
    )
    created_from_dt = _parse_datetime_filter(created_from)
    if created_from_dt is not None:
        base_query = base_query.filter(Order.created_at >= created_from_dt)
    created_to_dt = _parse_datetime_filter(created_to)
    if created_to_dt is not None:
        base_query = base_query.filter(Order.created_at <= created_to_dt)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerRebateLedger.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    order_ids = [int(_order.id) for _ledger, _order in rows if _order.id]
    attribution_rows = (
        db.query(PartnerOrderAttribution)
        .filter(PartnerOrderAttribution.order_id.in_(order_ids or [0]))
        .all()
    )
    channel_map = _channel_snapshot_map(db, channel_ids + [int(item.channel_id or 0) for item in attribution_rows])
    attr_map = {int(item.order_id): item for item in attribution_rows}
    items = []
    for ledger_row, order in rows:
        attr = attr_map.get(int(order.id))
        owner_channel = channel_map.get(int(ledger_row.channel_id or 0))
        items.append(
            {
                "order_no": order.order_no,
                "user_id": order.user_id,
                "package_name": attr.package_name if attr is not None else "",
                "order_status": order.status,
                "amount_cny": cny_to_api(order.amount_cny),
                "amount_fen": _cny_to_fen_int(order.amount_cny),
                "rebate_rate_bp": int(ledger_row.rebate_rate_bp or 0),
                "rebate_rate_pct": round(float(int(ledger_row.rebate_rate_bp or 0)) / 100.0, 2),
                "net_rebate_fen": int(ledger_row.rebate_amount_fen or 0),
                "net_rebate_cny": _fen_to_cny_api(ledger_row.rebate_amount_fen),
                "channel_id": int(ledger_row.channel_id or 0),
                "channel_name": owner_channel.name if owner_channel is not None else "",
                "channel_code": owner_channel.channel_code if owner_channel is not None else "",
                "source_channel_code": ledger_row.source_channel_code_snapshot,
                "created_at": order.created_at,
            }
        )
    return ok(data={"items": items, "pagination": paginate(total, page, page_size), "scope": _normalize_scope(scope)})


@router.get("/portal/ledger", response_model=APIResp)
def portal_ledger(
    request: Request,
    scope: str | None = Query(default="self"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    base_query = db.query(PartnerRebateLedger).filter(PartnerRebateLedger.channel_id.in_(channel_ids))
    created_from_dt = _parse_datetime_filter(created_from)
    if created_from_dt is not None:
        base_query = base_query.filter(PartnerRebateLedger.created_at >= created_from_dt)
    created_to_dt = _parse_datetime_filter(created_to)
    if created_to_dt is not None:
        base_query = base_query.filter(PartnerRebateLedger.created_at <= created_to_dt)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerRebateLedger.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    channel_map = _channel_snapshot_map(db, [int(row.channel_id or 0) for row in rows] + [int(row.source_channel_id or 0) for row in rows])
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "order_no": row.order_no,
                    "channel_id": int(row.channel_id or 0),
                    "channel_name": channel_map.get(int(row.channel_id or 0)).name if channel_map.get(int(row.channel_id or 0)) else "",
                    "channel_code": channel_map.get(int(row.channel_id or 0)).channel_code if channel_map.get(int(row.channel_id or 0)) else "",
                    "entry_type": row.entry_type.value,
                    "status": row.status.value,
                    "base_amount_fen": int(row.base_amount_fen or 0),
                    "base_amount_cny": _fen_to_cny_api(row.base_amount_fen),
                    "rebate_rate_bp": int(row.rebate_rate_bp or 0),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
                    "source_channel_id": row.source_channel_id,
                    "source_channel_code": row.source_channel_code_snapshot,
                    "statement_month": row.statement_month,
                    "statement_id": row.statement_id,
                    "note": row.note,
                    "created_at": row.created_at,
                    "settled_at": row.settled_at,
                }
                for row in rows
            ],
            "pagination": paginate(total, page, page_size),
            "scope": _normalize_scope(scope),
        }
    )


@router.get("/portal/statements", response_model=APIResp)
def portal_statements(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    base_query = db.query(PartnerMonthlyStatement).filter(PartnerMonthlyStatement.channel_id == channel.id)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerMonthlyStatement.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "statement_month": row.statement_month,
                    "status": row.status.value,
                    "total_orders": int(row.total_orders or 0),
                    "gross_amount_fen": int(row.gross_amount_fen or 0),
                    "gross_amount_cny": _fen_to_cny_api(row.gross_amount_fen),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
                    "settled_at": row.settled_at,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.get("/portal/withdrawals", response_model=APIResp)
def portal_withdrawals(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    base_query = db.query(PartnerWithdrawRequest).filter(PartnerWithdrawRequest.channel_id == channel.id)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerWithdrawRequest.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    summary = compute_partner_withdrawable_fen(db, channel_id=channel.id)
    return ok(
        data={
            "items": [_withdraw_item_payload(row) for row in rows],
            "pagination": paginate(total, page, page_size),
            "summary": summary,
        }
    )


@router.post("/portal/withdraw-apply", response_model=APIResp)
def portal_withdraw_apply(
    request: Request,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        apply_amount_cny = float(payload.get("apply_amount_cny") or 0)
    except Exception:
        return ok(data=None, message="提现金额格式错误")
    apply_amount_fen = int(round(apply_amount_cny * 100))
    row = create_partner_withdraw_request(
        db,
        channel=channel,
        apply_amount_fen=apply_amount_fen,
        note=str(payload.get("note") or ""),
    )
    db.commit()
    db.refresh(row)
    return ok(data=_withdraw_item_payload(row))


@router.get("/portal/subchannels", response_model=APIResp)
def portal_subchannels(
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    rows = (
        db.query(PartnerChannel)
        .filter(PartnerChannel.parent_channel_id == channel.id)
        .order_by(desc(PartnerChannel.id))
        .all()
    )
    return ok(data={"items": [_channel_item_payload(db, row, request=request) for row in rows]})


@router.get("/portal/channel-tree", response_model=APIResp)
def portal_channel_tree(
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    return ok(data={"item": _channel_tree_payload(db, channel=channel, request=request)})


@router.get("/portal/team-summary", response_model=APIResp)
def portal_team_summary(
    request: Request,
    scope: str | None = Query(default="subtree"),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    return ok(data=_team_summary_payload(db, channel_ids=channel_ids, scope=scope))


@router.get("/portal/analytics", response_model=APIResp)
def portal_analytics(
    request: Request,
    days: int = Query(default=14, ge=7, le=60),
    scope: str = Query(default="self"),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
    redis_client=Depends(get_redis),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    cache_key = _analytics_cache_key("portal", channel_id=int(channel.id), days=int(days), scope=_normalize_scope(scope))
    cached = _analytics_cache_get(redis_client, cache_key)
    if cached is not None:
        return ok(data=cached)
    data = _portal_partner_analytics_payload(db, channel=channel, days=days, scope=scope)
    _analytics_cache_set(redis_client, cache_key, data)
    return ok(data=data)


@router.get("/portal/customers", response_model=APIResp)
def portal_customers(
    request: Request,
    scope: str | None = Query(default="subtree"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    channel_ids = _scope_channel_ids(db, channel=channel, scope=scope)
    return ok(
        data=_customer_list_payload(
            db,
            channel_ids=channel_ids,
            page=page,
            page_size=page_size,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
    )


@router.post("/portal/subchannels", response_model=APIResp)
def portal_create_subchannel(
    request: Request,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    child = create_partner_channel(
        db,
        name=str(payload.get("name") or ""),
        contact_name=str(payload.get("contact_name") or ""),
        contact_phone=str(payload.get("contact_phone") or ""),
        channel_code=payload.get("channel_code"),
        rebate_rate_bp=payload.get("rebate_rate_bp", 0),
        parent_channel_id=channel.id,
    )
    child, portal_password = reset_partner_portal_password(db, channel=child)
    db.commit()
    db.refresh(child)
    return ok(data=_channel_secret_payload(db, child, portal_password=portal_password, request=request))


@router.patch("/portal/subchannels/{channel_id}", response_model=APIResp)
def portal_update_subchannel(
    channel_id: int,
    request: Request,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        child = _portal_managed_channel(channel, channel_id, db)
    except ValueError as exc:
        return ok(data=None, message=str(exc))
    child = update_partner_channel(
        db,
        channel=child,
        name=payload.get("name") if "name" in payload else None,
        contact_name=payload.get("contact_name") if "contact_name" in payload else None,
        contact_phone=payload.get("contact_phone") if "contact_phone" in payload else None,
        status=payload.get("status") if "status" in payload else None,
        rebate_rate_bp=payload.get("rebate_rate_bp") if "rebate_rate_bp" in payload else None,
    )
    db.commit()
    db.refresh(child)
    return ok(data=_channel_item_payload(db, child, request=request))


@router.get("/portal/subchannels/{channel_id}/policies", response_model=APIResp)
def portal_subchannel_policies(
    channel_id: int,
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        child = _portal_managed_channel(channel, channel_id, db)
    except ValueError as exc:
        return ok(data=None, message=str(exc))
    rows = (
        db.query(PartnerPolicy)
        .filter(PartnerPolicy.channel_id == child.id)
        .order_by(desc(PartnerPolicy.id))
        .all()
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "channel_id": row.channel_id,
                    "package_name": row.package_name or "*",
                    "rebate_rate_bp": int(row.rebate_rate_bp or 0),
                    "rebate_rate_pct": round(float(int(row.rebate_rate_bp or 0)) / 100.0, 2),
                    "is_active": bool(row.is_active),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]
        }
    )


@router.post("/portal/subchannels/{channel_id}/policy", response_model=APIResp)
def portal_upsert_subchannel_policy(
    channel_id: int,
    request: Request,
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        child = _portal_managed_channel(channel, channel_id, db)
    except ValueError as exc:
        return ok(data=None, message=str(exc))
    row = upsert_partner_policy(
        db,
        channel_id=int(child.id),
        package_name=payload.get("package_name"),
        rebate_rate_bp=payload.get("rebate_rate_bp", child.default_rebate_rate_bp),
        is_active=bool(payload.get("is_active", True)),
    )
    db.commit()
    db.refresh(row)
    return ok(
        data={
            "id": row.id,
            "channel_id": row.channel_id,
            "package_name": row.package_name or "*",
            "rebate_rate_bp": int(row.rebate_rate_bp or 0),
            "rebate_rate_pct": round(float(int(row.rebate_rate_bp or 0)) / 100.0, 2),
            "is_active": bool(row.is_active),
            "updated_at": row.updated_at,
        }
    )


def _portal_refresh_subchannel_link(
    channel_id: int,
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        child = _portal_managed_channel(channel, channel_id, db)
    except ValueError as exc:
        return ok(data=None, message=str(exc))
    child = rotate_partner_portal_token(db, channel=child)
    _clear_partner_session(auth_store, channel_id=int(child.id))
    db.commit()
    db.refresh(child)
    return ok(data=_channel_item_payload(db, child, request=request))


def _portal_reset_subchannel_password(
    channel_id: int,
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = _portal_channel(
        db,
        current_channel=current_channel,
        channel_code=request.query_params.get("ch") or request.query_params.get("channel_code"),
        portal_token=request.query_params.get("pk") or request.query_params.get("portal_token"),
    )
    try:
        child = _portal_managed_channel(channel, channel_id, db)
    except ValueError as exc:
        return ok(data=None, message=str(exc))
    child, portal_password = reset_partner_portal_password(db, channel=child)
    _clear_partner_session(auth_store, channel_id=int(child.id))
    db.commit()
    db.refresh(child)
    return ok(data=_channel_secret_payload(db, child, portal_password=portal_password, request=request))


@router.post("/portal/subchannels/{channel_id}/portal-link/refresh", response_model=APIResp)
def portal_refresh_subchannel_link(
    channel_id: int,
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
    auth_store=Depends(get_redis),
) -> APIResp:
    return _portal_refresh_subchannel_link(
        channel_id,
        request,
        db=db,
        current_channel=current_channel,
        auth_store=auth_store,
    )


@router.post("/portal/subchannels/{channel_id}/portal-password/reset", response_model=APIResp)
def portal_reset_subchannel_password(
    channel_id: int,
    request: Request,
    db: Session = Depends(db_dep),
    current_channel: PartnerChannel | None = Depends(optional_partner),
    auth_store=Depends(get_redis),
) -> APIResp:
    return _portal_reset_subchannel_password(
        channel_id,
        request,
        db=db,
        current_channel=current_channel,
        auth_store=auth_store,
    )


def _admin_refresh_partner_portal_link(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).with_for_update().first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    channel = rotate_partner_portal_token(db, channel=channel)
    _clear_partner_session(auth_store, channel_id=int(channel.id))
    db.commit()
    db.refresh(channel)
    return ok(data=_channel_item_payload(db, channel))


def _admin_reset_partner_portal_password(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    channel = db.query(PartnerChannel).filter(PartnerChannel.id == channel_id).with_for_update().first()
    if channel is None:
        return ok(data=None, message="渠道不存在")
    channel, portal_password = reset_partner_portal_password(
        db,
        channel=channel,
        plain_password=payload.get("portal_password"),
    )
    _clear_partner_session(auth_store, channel_id=int(channel.id))
    db.commit()
    db.refresh(channel)
    return ok(data=_channel_secret_payload(db, channel, portal_password=portal_password))


@router.post("/admin/channels/{channel_id}/portal-link/refresh", response_model=APIResp)
def admin_refresh_partner_portal_link(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    return _admin_refresh_partner_portal_link(
        channel_id,
        payload=payload,
        _=_,
        db=db,
        auth_store=auth_store,
    )


@router.post("/admin/channels/{channel_id}/portal-password/reset", response_model=APIResp)
def admin_reset_partner_portal_password(
    channel_id: int,
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
    auth_store=Depends(get_redis),
) -> APIResp:
    return _admin_reset_partner_portal_password(
        channel_id,
        payload=payload,
        _=_,
        db=db,
        auth_store=auth_store,
    )
