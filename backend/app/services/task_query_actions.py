from datetime import datetime
from pathlib import Path

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import Task, TaskStatus, TaskType
from app.pagination import paginate
from app.services.process_strategy_service import normalize_platform
from app.services.task_artifacts import resolve_task_artifact_path, safe_remove_task_artifact
from app.services.task_response_builder import build_detail_payload, build_list_item


def list_user_tasks(
    db: Session,
    *,
    user_id: int,
    page: int,
    page_size: int,
    task_type: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    base_query = db.query(Task).filter(Task.user_id == user_id)
    if task_type:
        try:
            base_query = base_query.filter(Task.task_type == TaskType(task_type))
        except Exception as exc:
            raise BizError(code=4101, message="任务类型不支持") from exc
    if platform:
        normalized_platform = normalize_platform(platform)
        base_query = base_query.filter(Task.platform == normalized_platform)
    if status:
        try:
            base_query = base_query.filter(Task.status == TaskStatus(status))
        except Exception as exc:
            raise BizError(code=4110, message="任务状态不支持") from exc
    if start_date:
        try:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            base_query = base_query.filter(Task.created_at >= dt)
        except Exception as exc:
            raise BizError(code=4111, message="开始日期格式错误，应为YYYY-MM-DD") from exc
    if end_date:
        try:
            dt = datetime.strptime(end_date, "%Y-%m-%d")
            dt = dt.replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Task.created_at <= dt)
        except Exception as exc:
            raise BizError(code=4112, message="结束日期格式错误，应为YYYY-MM-DD") from exc
    total = base_query.count()
    rows = (
        base_query.order_by(desc(Task.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": [build_list_item(row) for row in rows], "pagination": paginate(total, page, page_size)}


def get_user_task_detail(db: Session, *, user_id: int, task_id: int) -> dict:
    row = db.get(Task, task_id)
    if not row or row.user_id != user_id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    return build_detail_payload(row)


def get_user_task_download_path(db: Session, *, user_id: int, task_id: int) -> Path:
    row = db.get(Task, task_id)
    if not row or row.user_id != user_id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    if row.status != TaskStatus.COMPLETED or not row.output_path:
        raise BizError(code=4108, message="任务尚未完成")
    path = resolve_task_artifact_path(row.output_path)
    if path is None or not path.exists():
        raise BizError(code=4109, message="输出文件不存在")
    return path


def delete_user_task(db: Session, *, user_id: int, task_id: int) -> dict:
    row = db.get(Task, task_id)
    if not row or row.user_id != user_id:
        raise BizError(code=4041, message="任务不存在", http_status=404)
    if row.status == TaskStatus.RUNNING:
        raise BizError(code=4113, message="处理中任务不可删除")
    source_path = row.source_path
    report_path = row.report_path
    output_path = row.output_path
    db.delete(row)
    db.commit()
    safe_remove_task_artifact(source_path)
    safe_remove_task_artifact(report_path)
    safe_remove_task_artifact(output_path)
    return {"task_id": task_id, "deleted": True}
