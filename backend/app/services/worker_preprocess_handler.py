from datetime import datetime
from pathlib import Path

from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.services.partner_rebate_service import record_task_consume_rebate


def run_preprocess_submission(
    db,
    *,
    task_id: int,
    validate_report_content,
    extract_text_from_file,
    count_billable_chars,
    resolve_task_points_per_char,
    get_aigc_daily_quota,
    calc_task_cost_fen,
    change_credits,
) -> dict:
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        return {"ok": False, "reason": "task_not_found"}
    if task.status != TaskStatus.PREPROCESSING:
        return {"ok": True, "task_id": task.id, "status": task.status.value}
    claimed = (
        db.query(Task)
        .filter(Task.id == task_id, Task.status == TaskStatus.PREPROCESSING)
        .update(
            {
                Task.status: TaskStatus.PENDING,
                Task.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
    )
    db.flush()
    if claimed <= 0:
        current = db.query(Task).filter(Task.id == task_id).first()
        return {
            "ok": True,
            "task_id": task_id,
            "status": current.status.value if current is not None else TaskStatus.FAILED.value,
        }
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        return {"ok": False, "reason": "task_not_found"}

    if task.report_path:
        validate_report_content(task.task_type, Path(task.report_path))

    text = extract_text_from_file(Path(task.source_path))
    char_count = count_billable_chars(text)
    if char_count <= 0:
        raise ValueError("文档字符数为0，无法处理")

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
        raise ValueError("用户不存在")
    if user.credits < cost_fen:
        raise ValueError("通用点数不足，请先充值")

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
    result_json["billing"] = {
        "points_per_char": float(points_per_char),
        "free_applied": free_applied,
        "quota_before": quota_before,
        "cost_points": int(cost_fen),
    }
    task.char_count = char_count
    task.cost_credits = cost_fen
    task.result_json = result_json
    task.status = TaskStatus.QUEUED
    task.updated_at = datetime.utcnow()
    db.flush()
    return {"ok": True, "task_id": task.id, "status": TaskStatus.QUEUED.value}
