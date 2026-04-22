from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import current_user, db_dep, get_redis
from app.exceptions import BizError
from app.money import cny_to_api, fen_to_cny
from app.models import CreditTransaction, Notification, Task, TaskStatus, TaskType, User, UserInviteCode
from app.pagination import paginate
from app.responses import ok
from app.schemas import APIResp
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.process_strategy_service import sanitize_user_result_json
from app.services.task_artifacts import safe_remove_task_artifact
from app.security import auth_session_key

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


@router.get("/me", response_model=APIResp)
def me(user: User = Depends(current_user)) -> APIResp:
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
        }
    )


@router.get("/me/invite", response_model=APIResp)
def my_invite_info(
    user: User = Depends(current_user),
    db: Session = Depends(db_dep),
) -> APIResp:
    row = db.query(UserInviteCode).filter(UserInviteCode.user_id == user.id).with_for_update().first()
    if row is None:
        row = UserInviteCode(user_id=user.id, invite_code=_generate_invite_code(db))
        db.add(row)
        db.commit()
        db.refresh(row)
    return ok(data={"invite_code": row.invite_code, "invite_url_code": row.invite_code})


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
