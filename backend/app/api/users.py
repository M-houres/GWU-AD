from datetime import datetime, timedelta
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.api.auth import _get_promo_center_config
from app.config import get_settings
from app.constants import MAX_FILE_SIZE_MB
from app.deps import current_user, db_dep, get_redis
from app.exceptions import BizError
from app.money import cny_to_api, fen_to_cny
from app.models import (
    CreditType,
    CreditTransaction,
    Notification,
    PromoBenefitRecord,
    PromoBenefitStatus,
    PromoBenefitType,
    PromoShareSubmission,
    PromoShareSubmissionStatus,
    ReferralRelation,
    ShareTaskStatus,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserInviteCode,
    UserShareTaskSubmission,
)
from app.pagination import paginate
from app.responses import ok
from app.schemas import APIResp
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.credit_service import change_credits
from app.services.invite_service import bind_invite_code_for_user, ensure_user_invite_code
from app.services.partner_rebate_service import get_bound_channel_payload
from app.services.process_strategy_service import sanitize_user_result_json
from app.services.task_artifacts import (
    build_storage_name,
    safe_remove_task_artifact,
    save_upload_to,
    serialize_task_artifact_path,
)
from app.security import auth_session_key
from app.utils import safe_display_filename

router = APIRouter()
settings = get_settings()


def _fen_to_cny_api(value_fen: int) -> float:
    amount = fen_to_cny(int(value_fen or 0))
    return cny_to_api(amount or 0)


def _mask_phone(phone: str) -> str:
    raw = str(phone or "").strip()
    if len(raw) == 11:
        return f"{raw[:3]}****{raw[-4:]}"
    return raw


def _build_deleted_phone(user_id: int) -> str:
    return f"del{int(user_id):09d}"


def _generate_invite_code(db: Session) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(30):
        candidate = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = db.query(UserInviteCode.user_id).filter(UserInviteCode.invite_code == candidate).first()
        if not exists:
            return candidate
    raise BizError(code=4401, message="邀请码生成失败，请稍后重试")


def _promo_mask_phone(phone: str) -> str:
    return _mask_phone(phone)


def _serialize_referral_relation(db: Session, relation: ReferralRelation | None) -> dict | None:
    if relation is None:
        return None
    inviter = db.get(User, int(relation.inviter_id))
    return {
        "id": int(relation.id),
        "invite_code": relation.invite_code,
        "status": str(relation.status or "registered"),
        "created_at": relation.created_at,
        "inviter_user_id": int(relation.inviter_id),
        "inviter_phone": _promo_mask_phone(inviter.phone if inviter else ""),
        "inviter_nickname": str(inviter.nickname or "").strip() if inviter else "",
    }


def _serialize_invite_summary(db: Session, *, user: User, relation: ReferralRelation | None) -> dict:
    reward_rules = _get_promo_center_config(db).get("reward_rules", {}).get("invite", {})
    milestone_rules = reward_rules.get("milestones") if isinstance(reward_rules.get("milestones"), list) else []
    valid_invite_count = (
        db.query(func.count(ReferralRelation.id))
        .filter(
            ReferralRelation.inviter_id == user.id,
            ReferralRelation.register_reward_sent.is_(True),
        )
        .scalar()
        or 0
    )
    benefits = (
        db.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == user.id, PromoBenefitRecord.scene == "invite")
        .order_by(PromoBenefitRecord.id.asc())
        .all()
    )
    total_reward_points = sum(max(0, int(row.credit_delta or 0)) for row in benefits)
    inviter_reward_points = 0
    milestone_reward_points = 0
    invitee_bind_reward_granted = False
    earned_milestone_thresholds: set[int] = set()
    for row in benefits:
        benefit_code = str(row.benefit_code or "").strip()
        if benefit_code.endswith("invitee-bind"):
            invitee_bind_reward_granted = True
        elif benefit_code.endswith("inviter-valid"):
            inviter_reward_points += max(0, int(row.credit_delta or 0))
        elif benefit_code.startswith("milestone:"):
            milestone_reward_points += max(0, int(row.credit_delta or 0))
            parts = benefit_code.split(":")
            if len(parts) >= 3:
                try:
                    earned_milestone_thresholds.add(int(parts[-1]))
                except Exception:
                    pass
    earned_milestones = []
    next_milestone = None
    for item in milestone_rules:
        threshold = max(0, int(item.get("threshold") or 0))
        reward_points = max(0, int(item.get("reward_points") or 0))
        label = str(item.get("label") or "").strip()[:48] or f"邀请满 {threshold} 人"
        milestone_item = {
            "threshold": threshold,
            "reward_points": reward_points,
            "label": label,
            "earned": threshold in earned_milestone_thresholds,
            "remaining_count": max(0, threshold - int(valid_invite_count)),
        }
        if milestone_item["earned"]:
            earned_milestones.append(milestone_item)
        elif next_milestone is None and threshold > 0:
            next_milestone = milestone_item
    invitee_reward_points = max(0, int(reward_rules.get("invitee_bind_reward_points") or 0))
    return {
        "valid_invite_count": int(valid_invite_count),
        "invitee_bind_reward_points": invitee_reward_points,
        "invitee_bind_reward_granted": bool(invitee_bind_reward_granted),
        "inviter_reward_points_total": int(inviter_reward_points),
        "milestone_reward_points_total": int(milestone_reward_points),
        "total_reward_points": int(total_reward_points),
        "earned_milestones": earned_milestones,
        "next_milestone": next_milestone,
        "bound_relation_id": int(relation.id) if relation else None,
    }


def _serialize_like_submission(row: UserShareTaskSubmission) -> dict:
    return {
        "id": int(row.id),
        "platform": str(row.platform or "").strip(),
        "status": row.status.value if hasattr(row.status, "value") else str(row.status or "pending"),
        "reward_credits": int(row.reward_credits or 0),
        "share_text": str(row.share_text or ""),
        "original_filename": str(row.original_filename or ""),
        "screenshot_path": str(row.screenshot_path or ""),
        "review_note": row.review_note,
        "reviewed_at": row.reviewed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_create_submission(row: PromoShareSubmission) -> dict:
    return {
        "id": int(row.id),
        "platform": str(row.platform or "").strip(),
        "tier_key": str(row.tier_key or "").strip(),
        "share_link": str(row.share_link or "").strip(),
        "payout_account": str(row.payout_account or "").strip(),
        "payout_name": str(row.payout_name or "").strip(),
        "note": str(row.note or ""),
        "status": row.status.value if hasattr(row.status, "value") else str(row.status or "submitted"),
        "reward_credits": int(row.reward_credits or 0),
        "reward_amount_cny": float(row.reward_amount_cny or 0),
        "coupon_name": row.coupon_name,
        "coupon_count": int(row.coupon_count or 0),
        "review_note": row.review_note,
        "reviewed_at": row.reviewed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _promo_code_row(db: Session, *, user_id: int) -> UserInviteCode:
    row = db.query(UserInviteCode).filter(UserInviteCode.user_id == user_id).with_for_update().first()
    if row is None:
        row = UserInviteCode(user_id=user_id, invite_code=_generate_invite_code(db))
        db.add(row)
        db.flush()
    return row


def _invite_benefit_code(*parts: object) -> str:
    return ":".join(str(part).strip() for part in parts if str(part).strip())[:64]


def _resolve_promo_upload_name(upload: UploadFile | None, *, provided_name: str = "", fallback_name: str) -> str:
    normalized_provided = safe_display_filename(provided_name) if provided_name else ""
    normalized_upload_name = safe_display_filename(upload.filename) if upload and upload.filename else ""
    if normalized_provided:
        if Path(normalized_provided).suffix:
            return normalized_provided
        upload_ext = Path(normalized_upload_name).suffix.lower()
        return f"{normalized_provided}{upload_ext}" if upload_ext else normalized_provided
    return normalized_upload_name or safe_display_filename(fallback_name)


def _promo_store_upload(upload: UploadFile, *, folder: str, provided_name: str = "") -> tuple[str, str]:
    filename = _resolve_promo_upload_name(upload, provided_name=provided_name, fallback_name="promo-screenshot.png")
    if not filename:
        raise BizError(code=4101, message="请先选择截图文件")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise BizError(code=4104, message="截图仅支持 png、jpg、jpeg、webp")
    original_name, unique_name = build_storage_name(filename, "promo-screenshot.png")
    target_path = settings.upload_dir / "promo" / folder / unique_name
    save_upload_to(target_path, upload, MAX_FILE_SIZE_MB * 1024 * 1024)
    return serialize_task_artifact_path(target_path) or str(target_path), original_name


@router.get("/me", response_model=APIResp)
def me(user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    return ok(
        data={
            "id": user.id,
            "phone": _mask_phone(user.phone),
            "nickname": user.nickname,
            "balance_fen": int(user.credits or 0),
            "balance_cny": _fen_to_cny_api(user.credits or 0),
            "credits": user.credits,
            "source": user.source,
            "created_at": user.created_at,
            "partner_tracking": get_bound_channel_payload(db, user_id=int(user.id)),
        }
    )


@router.get("/me/invite", response_model=APIResp)
def my_invite_info(
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = ensure_user_invite_code(db, user_id=int(user.id))
    relation = db.query(ReferralRelation).filter(ReferralRelation.invitee_id == user.id).first()
    db.commit()
    return ok(
        data={
            "invite_code": row.invite_code,
            "invite_url_code": row.invite_code,
            "invite_link": f"/pages/home/index?ref={row.invite_code}",
            "bound_relation": _serialize_referral_relation(db, relation),
            "invite_summary": _serialize_invite_summary(db, user=user, relation=relation),
        }
    )


@router.get("/me/invite-code", response_model=APIResp)
def my_invite_code_compat(
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = ensure_user_invite_code(db, user_id=int(user.id))
    db.commit()
    return ok(
        data={
            "invite_code": row.invite_code,
            "invite_link": f"/pages/home/index?ref={row.invite_code}",
        }
    )


@router.post("/me/invite/bind", response_model=APIResp)
def bind_invite_code(
    payload: dict,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    relation = bind_invite_code_for_user(
        db,
        user=user,
        invite_code=str(payload.get("invite_code", "")).strip().upper(),
        source="web",
        strict=True,
    )
    db.commit()
    if relation is not None:
        db.refresh(relation)
    return ok(
        data={
            "bound_relation": _serialize_referral_relation(db, relation),
            "invite_summary": _serialize_invite_summary(db, user=user, relation=relation),
        }
    )


@router.get("/me/promo/like-submissions", response_model=APIResp)
def my_like_submissions(
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    rows = (
        db.query(UserShareTaskSubmission)
        .filter(UserShareTaskSubmission.user_id == user.id)
        .order_by(desc(UserShareTaskSubmission.updated_at), desc(UserShareTaskSubmission.id))
        .all()
    )
    return ok(data={"items": [_serialize_like_submission(row) for row in rows]})


@router.post("/me/promo/like-submissions", response_model=APIResp)
def submit_like_screenshot(
    platform: str = Form(...),
    share_text: str = Form(default=""),
    screenshot_name: str = Form(default=""),
    screenshot: UploadFile = File(...),
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    normalized_platform = str(platform or "").strip().lower()[:32]
    if not normalized_platform:
        raise BizError(code=4406, message="请选择活动平台")
    screenshot_path, original_name = _promo_store_upload(screenshot, folder="like", provided_name=screenshot_name)
    row = (
        db.query(UserShareTaskSubmission)
        .filter(
            UserShareTaskSubmission.user_id == user.id,
            UserShareTaskSubmission.platform == normalized_platform,
        )
        .first()
    )
    if row is None:
        row = UserShareTaskSubmission(
            user_id=int(user.id),
            platform=normalized_platform,
            screenshot_path=screenshot_path,
            original_filename=original_name,
            share_text=str(share_text or "").strip()[:500],
        )
        db.add(row)
    else:
        previous_path = str(row.screenshot_path or "").strip()
        row.screenshot_path = screenshot_path
        row.original_filename = original_name
        row.share_text = str(share_text or "").strip()[:500]
        row.status = ShareTaskStatus.PENDING
        row.review_note = None
        row.reviewed_at = None
        row.reviewed_by = None
        if previous_path and previous_path != screenshot_path:
            safe_remove_task_artifact(previous_path, warn_on_untrusted=False)
    db.commit()
    db.refresh(row)
    return ok(data={"item": _serialize_like_submission(row)})


@router.get("/me/promo/create-submissions", response_model=APIResp)
def my_create_submissions(
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    rows = (
        db.query(PromoShareSubmission)
        .filter(PromoShareSubmission.user_id == user.id)
        .order_by(desc(PromoShareSubmission.updated_at), desc(PromoShareSubmission.id))
        .all()
    )
    return ok(data={"items": [_serialize_create_submission(row) for row in rows]})


@router.post("/me/promo/create-submissions", response_model=APIResp)
def submit_create_link(
    payload: dict,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    platform = str(payload.get("platform", "")).strip().lower()[:32]
    share_link = str(payload.get("share_link", "")).strip()[:500]
    tier_key = str(payload.get("tier_key", "")).strip()[:24] or "default"
    payout_account = str(payload.get("payout_account", "")).strip()[:120]
    payout_name = str(payload.get("payout_name", "")).strip()[:120]
    note = str(payload.get("note", "")).strip()[:500]
    if not platform:
        raise BizError(code=4407, message="请选择创作平台")
    if not share_link:
        raise BizError(code=4408, message="请填写作品链接")

    row = (
        db.query(PromoShareSubmission)
        .filter(PromoShareSubmission.user_id == user.id, PromoShareSubmission.platform == platform)
        .first()
    )
    if row is None:
        row = PromoShareSubmission(
            user_id=int(user.id),
            platform=platform,
            tier_key=tier_key,
            share_link=share_link,
            payout_account=payout_account,
            payout_name=payout_name,
            note=note,
            status=PromoShareSubmissionStatus.SUBMITTED,
        )
        db.add(row)
    else:
        row.tier_key = tier_key
        row.share_link = share_link
        row.payout_account = payout_account
        row.payout_name = payout_name
        row.note = note
        row.status = PromoShareSubmissionStatus.SUBMITTED
        row.review_note = None
        row.reviewed_at = None
        row.reviewed_by = None
    db.commit()
    db.refresh(row)
    return ok(data={"item": _serialize_create_submission(row)})


@router.patch("/me", response_model=APIResp)
def update_me(
    payload: dict,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    nickname = str(payload.get("nickname", "")).strip()[:64]
    user.nickname = nickname
    db.commit()
    return ok(
        data={
            "id": user.id,
            "phone": _mask_phone(user.phone),
            "nickname": user.nickname,
            "balance_fen": int(user.credits or 0),
            "balance_cny": _fen_to_cny_api(user.credits or 0),
            "credits": user.credits,
            "source": user.source,
            "created_at": user.created_at,
            "partner_tracking": get_bound_channel_payload(db, user_id=int(user.id)),
        }
    )


@router.delete("/me", response_model=APIResp)
def delete_me(
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
    redis_client=Depends(get_redis),
) -> APIResp:
    locked_user = db.query(User).filter(User.id == user.id).with_for_update().first()
    if locked_user is None:
        raise BizError(code=4040, message="用户不存在", http_status=404)

    tasks = db.query(Task).filter(Task.user_id == locked_user.id).all()
    for task in tasks:
        safe_remove_task_artifact(task.source_path, warn_on_untrusted=False)
        safe_remove_task_artifact(task.report_path, warn_on_untrusted=False)
        safe_remove_task_artifact(task.output_path, warn_on_untrusted=False)
        db.delete(task)

    notifications = db.query(Notification).filter(Notification.user_id == locked_user.id).all()
    for row in notifications:
        db.delete(row)

    locked_user.phone = _build_deleted_phone(locked_user.id)
    locked_user.nickname = "已注销用户"
    locked_user.openid = None
    locked_user.wechat_unionid = None
    locked_user.wechat_openid_web = None
    locked_user.wechat_openid_mp = None
    locked_user.is_banned = True
    db.commit()

    redis_client.delete(auth_session_key("user", str(locked_user.id)))
    response.delete_cookie("gw_user_access", path="/")
    response.delete_cookie(settings.user_refresh_cookie_name, path="/api/v1/auth")
    return ok(data={"deleted": True})


@router.get("/me/summary", response_model=APIResp)
def me_summary(user: User = Depends(current_user), db: Session = Depends(db_dep)) -> APIResp:
    recent_window = datetime.now() - timedelta(days=7)
    task_total = db.query(Task.id).filter(Task.user_id == user.id).count()
    recent_task_count = (
        db.query(Task.id)
        .filter(Task.user_id == user.id, Task.created_at >= recent_window)
        .count()
    )
    tx_total = db.query(CreditTransaction.id).filter(CreditTransaction.user_id == user.id).count()
    income_total = (
        db.query(func.coalesce(func.sum(CreditTransaction.delta), 0))
        .filter(CreditTransaction.user_id == user.id, CreditTransaction.delta >= 0)
        .scalar()
        or 0
    )
    outcome_total = (
        db.query(func.coalesce(func.sum(CreditTransaction.delta), 0))
        .filter(CreditTransaction.user_id == user.id, CreditTransaction.delta < 0)
        .scalar()
        or 0
    )

    type_counts = {item.value: 0 for item in TaskType}
    for task_type, count in (
        db.query(Task.task_type, func.count(Task.id))
        .filter(Task.user_id == user.id)
        .group_by(Task.task_type)
        .all()
    ):
        type_counts[task_type.value if isinstance(task_type, TaskType) else str(task_type)] = int(count)

    status_counts = {item.value: 0 for item in TaskStatus}
    for status, count in (
        db.query(Task.status, func.count(Task.id))
        .filter(Task.user_id == user.id)
        .group_by(Task.status)
        .all()
    ):
        status_counts[status.value if isinstance(status, TaskStatus) else str(status)] = int(count)

    last_task = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(desc(Task.id))
        .first()
    )
    recent_tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id)
        .order_by(desc(Task.id))
        .limit(6)
        .all()
    )
    recent_transactions = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id)
        .order_by(desc(CreditTransaction.id))
        .limit(6)
        .all()
    )

    return ok(
        data={
            "task_counts": {
                "total": int(task_total),
                "recent_7d": int(recent_task_count),
                "by_type": type_counts,
                "by_status": status_counts,
                "last_created_at": last_task.created_at if last_task else None,
            },
            "credit_overview": {
                "transaction_count": int(tx_total),
                "income_total_fen": int(income_total),
                "income_total_cny": _fen_to_cny_api(income_total),
                "outcome_total_fen": abs(int(outcome_total)),
                "outcome_total_cny": _fen_to_cny_api(abs(int(outcome_total))),
                "income_total": int(income_total),
                "outcome_total": abs(int(outcome_total)),
            },
            "aigc_quota": get_aigc_daily_quota(db, user_id=user.id),
            "partner_tracking": get_bound_channel_payload(db, user_id=int(user.id)),
            "recent_tasks": [
                {
                    "id": row.id,
                    "task_type": row.task_type.value,
                    "platform": row.platform,
                    "status": row.status.value,
                    "source_filename": row.source_filename,
                    "char_count": row.char_count,
                    "cost_fen": int(row.cost_credits or 0),
                    "cost_points": int(row.cost_credits or 0),
                    "cost_credits": row.cost_credits,
                    "result_json": sanitize_user_result_json(row.result_json),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in recent_tasks
            ],
            "recent_transactions": [
                {
                    "id": row.id,
                    "tx_type": row.tx_type.value,
                    "delta_fen": int(row.delta or 0),
                    "delta_cny": _fen_to_cny_api(row.delta or 0),
                    "balance_before_fen": int(row.balance_before or 0),
                    "balance_before_cny": _fen_to_cny_api(row.balance_before or 0),
                    "balance_after_fen": int(row.balance_after or 0),
                    "balance_after_cny": _fen_to_cny_api(row.balance_after or 0),
                    "delta": row.delta,
                    "balance_before": row.balance_before,
                    "balance_after": row.balance_after,
                    "reason": row.reason,
                    "created_at": row.created_at,
                }
                for row in recent_transactions
            ],
        }
    )


@router.get("/me/credit-transactions", response_model=APIResp)
def my_credit_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tx_type: str | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(CreditTransaction).filter(CreditTransaction.user_id == user.id)
    if tx_type:
        base_query = base_query.filter(CreditTransaction.tx_type == tx_type)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(CreditTransaction.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": row.id,
            "tx_type": row.tx_type.value,
            "delta": row.delta,
            "balance_before": row.balance_before,
            "balance_after": row.balance_after,
                "reason": row.reason,
                "related_id": row.related_id,
                "source": row.source,
                "created_at": row.created_at,
            }
        for row in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})


@router.get("/me/notifications", response_model=APIResp)
def my_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    base_query = db.query(Notification).filter(Notification.user_id == user.id)
    total = base_query.count()
    rows = (
        base_query.order_by(desc(Notification.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "id": n.id,
            "title": n.title,
            "content": n.content,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]
    return ok(data={"items": items, "pagination": paginate(total, page, page_size)})
