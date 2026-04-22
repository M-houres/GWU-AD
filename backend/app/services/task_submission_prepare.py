from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.billing_rules_service import calc_task_cost_fen, resolve_task_points_per_char
from app.services.credit_service import change_credits
from app.services.partner_rebate_service import record_task_consume_rebate
from app.services.task_report_validation import validate_full_report_content
from app.utils import count_billable_chars, extract_text_from_file


def validate_report_content(task_type: TaskType, path: Path) -> None:
    message = validate_full_report_content(task_type, path)
    if not message:
        return
    if task_type == TaskType.DEDUP:
        raise BizError(code=4114, message=message, http_status=422)
    raise BizError(code=4115, message=message, http_status=422)


def prepare_task_for_processing(db: Session, *, task: Task) -> dict:
    if task.report_path:
        validate_report_content(task.task_type, Path(task.report_path))

    text = extract_text_from_file(Path(task.source_path))
    char_count = count_billable_chars(text)
    if char_count <= 0:
        raise BizError(code=4102, message="上传文件为空")

    points_per_char = resolve_task_points_per_char(db, task.task_type)
    quota_before = (
        get_aigc_daily_quota(db, user_id=task.user_id, submitted_delta=-1)
        if task.task_type == TaskType.AIGC_DETECT
        else None
    )
    free_applied = bool(quota_before and quota_before["free_remaining_today"] > 0)
    cost_fen = 0 if free_applied else calc_task_cost_fen(char_count, points_per_char)

    user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
    if user is None:
        raise BizError(code=4001, message="用户不存在")

    change_credits(
        db,
        user,
        tx_type=CreditType.TASK_CONSUME,
        delta=-cost_fen,
        reason="AIGC每日免费额度抵扣" if free_applied else f"{task.task_type.value}任务提交扣费",
        related_id=f"task:{task.id}",
        source=task.source,
    )
    record_task_consume_rebate(
        db,
        task_id=task.id,
        user_id=task.user_id,
        cost_fen=cost_fen,
        task_type=task.task_type.value,
    )

    result_json = dict(task.result_json or {})
    billing = {
        "points_per_char": float(points_per_char),
        "free_applied": free_applied,
        "quota_before": quota_before,
        "cost_fen": int(cost_fen),
        "cost_points": int(cost_fen),
    }
    result_json["billing"] = billing
    task.char_count = char_count
    task.cost_credits = cost_fen
    task.result_json = result_json
    task.status = TaskStatus.PENDING
    task.updated_at = datetime.utcnow()
    db.flush()

    return {
        "points_per_char": float(points_per_char),
        "free_applied": free_applied,
        "quota": quota_before,
        "cost_fen": int(cost_fen),
        "cost_points": int(cost_fen),
    }


def initial_billing_payload(db: Session, *, user_id: int, task_type: TaskType) -> dict:
    quota = get_aigc_daily_quota(db, user_id=user_id) if task_type == TaskType.AIGC_DETECT else None
    return {
        "points_per_char": float(resolve_task_points_per_char(db, task_type)),
        "free_applied": bool(quota and quota["free_remaining_today"] > 0),
        "quota": quota,
    }
