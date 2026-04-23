from sqlalchemy.orm import Session

from app.models import Task, TaskStatus, User
from app.services.billing_rules_service import resolve_task_points_per_char
from app.services.process_strategy_service import sanitize_user_result_json
from app.services.task_filename import build_task_filename_pair, build_task_result_filename


def build_submit_payload(
    db: Session,
    *,
    task: Task,
    strategy: dict | None = None,
    billing_payload: dict | None = None,
    idempotent: bool = False,
    dispatch_mode: str | None = None,
    balance_after: int | None = None,
) -> dict:
    result_json = dict(task.result_json or {})
    billing = billing_payload or result_json.get("billing")
    if not isinstance(billing, dict):
        billing = {
            "points_per_char": float(resolve_task_points_per_char(db, task.task_type)),
            "free_applied": False,
            "quota": None,
            "cost_fen": int(task.cost_credits or 0),
            "cost_points": int(task.cost_credits or 0),
        }
    if balance_after is None:
        user_row = db.get(User, task.user_id)
        balance_after = int(user_row.credits) if user_row is not None else None
    result_filename = build_task_result_filename(task.task_type, task.source_filename, task.output_path)
    payload = {
        "id": task.id,
        "task_type": task.task_type.value,
        "platform": task.platform,
        "source": task.source,
        "status": task.status.value,
        "source_filename": task.source_filename,
        "result_filename": result_filename,
        "filename_pair": build_task_filename_pair(task.source_filename, result_filename),
        "has_report": bool(task.report_path),
        "char_count": int(task.char_count or 0),
        "cost_credits": int(task.cost_credits or 0),
        "cost_fen": int(task.cost_credits or 0),
        "cost_points": int(task.cost_credits or 0),
        "refund_done": bool(task.refund_done),
        "result_json": sanitize_user_result_json(task.result_json),
        "billing": billing,
        "balance_after": balance_after,
        "balance_after_fen": balance_after,
        "idempotent": bool(idempotent),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
    if strategy is not None:
        payload["estimated_time"] = int(strategy.get("timeout_sec", 300))
    if dispatch_mode is not None:
        payload["dispatch_mode"] = dispatch_mode
    return payload


def build_recover_payload(task: Task) -> dict:
    result_filename = build_task_result_filename(task.task_type, task.source_filename, task.output_path)
    return {
        "id": task.id,
        "task_type": task.task_type.value,
        "platform": task.platform,
        "status": task.status.value,
        "source_filename": task.source_filename,
        "result_filename": result_filename,
        "filename_pair": build_task_filename_pair(task.source_filename, result_filename),
        "cost_credits": task.cost_credits,
        "cost_fen": int(task.cost_credits or 0),
        "cost_points": int(task.cost_credits or 0),
        "refund_done": bool(task.refund_done),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def build_list_item(task: Task) -> dict:
    result_filename = build_task_result_filename(task.task_type, task.source_filename, task.output_path)
    return {
        "id": task.id,
        "task_type": task.task_type.value,
        "platform": task.platform,
        "source": task.source,
        "status": task.status.value,
        "source_filename": task.source_filename,
        "result_filename": result_filename,
        "filename_pair": build_task_filename_pair(task.source_filename, result_filename),
        "has_report": bool(task.report_path),
        "char_count": task.char_count,
        "cost_credits": task.cost_credits,
        "cost_fen": int(task.cost_credits or 0),
        "cost_points": int(task.cost_credits or 0),
        "refund_done": bool(task.refund_done),
        "result_json": sanitize_user_result_json(task.result_json),
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def build_detail_payload(task: Task) -> dict:
    payload = build_list_item(task)
    payload["download_ready"] = bool(task.status == TaskStatus.COMPLETED and task.output_path)
    return payload
