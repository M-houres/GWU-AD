from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.deps import db_dep, require_admin_permission
from app.models import (
    AdminUser,
    Order,
    PartnerChannel,
    PartnerLedgerStatus,
    PartnerMonthlyStatement,
    PartnerOrderAttribution,
    PartnerPolicy,
    PartnerRebateLedger,
    PartnerWithdrawRequest,
    PartnerWithdrawStatus,
)
from app.money import cny_to_api, fen_to_cny
from app.pagination import paginate
from app.responses import ok
from app.schemas import APIResp
from app.services.partner_rebate_service import (
    authenticate_partner_portal,
    build_channel_links,
    compute_partner_withdrawable_fen,
    create_partner_channel,
    create_partner_withdraw_request,
    generate_monthly_statement,
    get_partner_portal_overview,
    mark_partner_withdraw_paid,
    review_partner_withdraw_request,
    settle_monthly_statement,
    update_partner_channel,
    upsert_partner_policy,
)

router = APIRouter()


def _fen_to_cny_api(value_fen: int) -> float:
    return cny_to_api(fen_to_cny(int(value_fen or 0)) or 0)


def _cny_to_fen_int(value) -> int:
    amount = cny_to_api(value)
    return int(round(float(amount) * 100))


def _channel_item_payload(db: Session, channel: PartnerChannel) -> dict:
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
    links = build_channel_links(channel)
    return {
        "id": channel.id,
        "channel_code": channel.channel_code,
        "name": channel.name,
        "contact_name": channel.contact_name,
        "contact_phone": channel.contact_phone,
        "status": channel.status,
        "default_rebate_rate_bp": int(channel.default_rebate_rate_bp or 0),
        "default_rebate_rate_pct": round(float(int(channel.default_rebate_rate_bp or 0)) / 100.0, 2),
        "order_token": channel.order_token,
        "portal_token": channel.portal_token,
        "order_link": links["order_link"],
        "portal_link": links["portal_link"],
        "pending_rebate_fen": int(pending),
        "pending_rebate_cny": _fen_to_cny_api(pending),
        "settled_rebate_fen": int(settled),
        "settled_rebate_cny": _fen_to_cny_api(settled),
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


def _withdraw_item_payload(row: PartnerWithdrawRequest) -> dict:
    return {
        "id": row.id,
        "request_no": row.request_no,
        "channel_id": row.channel_id,
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


@router.post("/admin/channels", response_model=APIResp)
def admin_create_partner_channel(
    payload: dict = Body(default_factory=dict),
    _: AdminUser = Depends(require_admin_permission("configs:manage")),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = create_partner_channel(
        db,
        name=str(payload.get("name") or ""),
        contact_name=str(payload.get("contact_name") or ""),
        contact_phone=str(payload.get("contact_phone") or ""),
        channel_code=payload.get("channel_code"),
        rebate_rate_bp=payload.get("rebate_rate_bp", 1500),
    )
    db.commit()
    db.refresh(channel)
    return ok(data=_channel_item_payload(db, channel))


@router.get("/admin/channels", response_model=APIResp)
def admin_list_partner_channels(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    _: AdminUser = Depends(require_admin_permission("orders:view")),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(PartnerChannel)
    normalized_status = str(status or "").strip().lower()
    if normalized_status in {"active", "disabled"}:
        base_query = base_query.filter(PartnerChannel.status == normalized_status)
    normalized_keyword = str(keyword or "").strip()
    if normalized_keyword:
        like = f"%{normalized_keyword}%"
        base_query = base_query.filter((PartnerChannel.channel_code.like(like)) | (PartnerChannel.name.like(like)))
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerChannel.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        data={
            "items": [_channel_item_payload(db, row) for row in rows],
            "pagination": paginate(total, page, page_size),
        }
    )


@router.patch("/admin/channels/{channel_id}", response_model=APIResp)
def admin_update_partner_channel(
    channel_id: int,
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
    return ok(data=_channel_item_payload(db, channel))


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
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "channel_id": row.channel_id,
                    "order_no": row.order_no,
                    "entry_type": row.entry_type.value,
                    "status": row.status.value,
                    "base_amount_fen": int(row.base_amount_fen or 0),
                    "base_amount_cny": _fen_to_cny_api(row.base_amount_fen),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
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
    return ok(data={"items": [_withdraw_item_payload(row) for row in rows], "pagination": paginate(total, page, page_size)})


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
    channel_code: str,
    portal_token: str,
    db: Session,
) -> PartnerChannel:
    return authenticate_partner_portal(db, channel_code=channel_code, portal_token=portal_token)


@router.get("/portal/overview", response_model=APIResp)
def portal_overview(
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    statement_month: str | None = Query(default=None),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
    return ok(data=get_partner_portal_overview(db, channel=channel, statement_month=statement_month))


@router.get("/portal/orders", response_model=APIResp)
def portal_orders(
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
    base_query = (
        db.query(PartnerOrderAttribution, Order)
        .join(Order, Order.id == PartnerOrderAttribution.order_id)
        .filter(PartnerOrderAttribution.channel_id == channel.id)
    )
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerOrderAttribution.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    order_nos = [str(_order.order_no or "") for _attr, _order in rows if _order.order_no]
    ledger_sum_rows = (
        db.query(
            PartnerRebateLedger.order_no,
            func.coalesce(func.sum(PartnerRebateLedger.rebate_amount_fen), 0),
        )
        .filter(
            PartnerRebateLedger.channel_id == channel.id,
            PartnerRebateLedger.order_no.in_(order_nos or ["-"]),
        )
        .group_by(PartnerRebateLedger.order_no)
        .all()
    )
    net_map = {str(order_no): int(amount or 0) for order_no, amount in ledger_sum_rows}
    items = []
    for attr, order in rows:
        net_rebate_fen = int(net_map.get(str(order.order_no), 0))
        items.append(
            {
                "order_no": order.order_no,
                "user_id": order.user_id,
                "package_name": attr.package_name,
                "order_status": order.status,
                "amount_cny": cny_to_api(order.amount_cny),
                "amount_fen": _cny_to_fen_int(order.amount_cny),
                "rebate_rate_bp": int(attr.rebate_rate_bp or 0),
                "rebate_rate_pct": round(float(int(attr.rebate_rate_bp or 0)) / 100.0, 2),
                "net_rebate_fen": net_rebate_fen,
                "net_rebate_cny": _fen_to_cny_api(net_rebate_fen),
                "created_at": order.created_at,
            }
        )
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/portal/ledger", response_model=APIResp)
def portal_ledger(
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
    base_query = db.query(PartnerRebateLedger).filter(PartnerRebateLedger.channel_id == channel.id)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(PartnerRebateLedger.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        data={
            "items": [
                {
                    "id": row.id,
                    "order_no": row.order_no,
                    "entry_type": row.entry_type.value,
                    "status": row.status.value,
                    "base_amount_fen": int(row.base_amount_fen or 0),
                    "base_amount_cny": _fen_to_cny_api(row.base_amount_fen),
                    "rebate_amount_fen": int(row.rebate_amount_fen or 0),
                    "rebate_amount_cny": _fen_to_cny_api(row.rebate_amount_fen),
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


@router.get("/portal/statements", response_model=APIResp)
def portal_statements(
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
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
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
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
    ch: str = Query(min_length=3, max_length=32),
    pk: str = Query(min_length=16, max_length=128),
    payload: dict = Body(default_factory=dict),
    db: Session = Depends(db_dep),
) -> APIResp:
    channel = _portal_channel(ch, pk, db)
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
