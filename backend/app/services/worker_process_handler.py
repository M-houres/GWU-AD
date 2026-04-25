from datetime import datetime
from pathlib import Path

from app.models import Task, TaskStatus
from app.services.task_artifacts import resolve_task_artifact_path, serialize_task_artifact_path


def claim_process_task(db, *, task_id: int) -> dict:
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        return {"ok": False, "reason": "task_not_found"}
    if task.status == TaskStatus.COMPLETED:
        return {"ok": True, "task_id": task.id, "status": task.status.value}
    if task.status not in {TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING}:
        return {"ok": False, "task_id": task.id, "reason": f"invalid_status:{task.status.value}"}
    if task.status == TaskStatus.RUNNING:
        return {"ok": True, "task_id": task.id, "status": task.status.value}

    claimed = (
        db.query(Task)
        .filter(Task.id == task_id, Task.status.in_((TaskStatus.PENDING, TaskStatus.QUEUED)))
        .update(
            {
                Task.status: TaskStatus.RUNNING,
                Task.error_message: None,
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
    snapshot = {
        "id": task.id,
        "user_id": task.user_id,
        "task_type": task.task_type,
        "platform": task.platform,
        "source_path": task.source_path,
        "report_path": task.report_path,
        "source_filename": task.source_filename,
        "processing_mode": task.processing_mode,
        "result_json": dict(task.result_json or {}),
    }
    return {"ok": True, "snapshot": snapshot}


def build_process_output_path(task_snapshot: dict, *, settings) -> Path:
    source_path = resolve_task_artifact_path(task_snapshot["source_path"]) or Path(task_snapshot["source_path"])
    output_dir = settings.output_dir / str(task_snapshot["user_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_ext = ".pdf" if task_snapshot["task_type"].value == "aigc_detect" else source_path.suffix.lower()
    if not output_ext:
        output_ext = ".txt"
    return output_dir / f"task_{task_snapshot['id']}_result{output_ext}"


def run_processing_engine(process_db, *, task_snapshot: dict, output_path: Path, processing_engine_cls):
    source_path = resolve_task_artifact_path(task_snapshot["source_path"])
    if source_path is None:
        raise FileNotFoundError("任务原文不存在")
    report_path = resolve_task_artifact_path(task_snapshot["report_path"]) if task_snapshot["report_path"] else None
    engine = processing_engine_cls(process_db)
    result = engine.process(
        task_snapshot["task_type"],
        task_snapshot["platform"],
        source_path,
        output_path,
        task_id=task_snapshot["id"],
        report_path=report_path,
        processing_mode=task_snapshot["processing_mode"],
    )
    process_db.flush()
    return result


def finalize_processed_task(db, *, task_id: int, result, task_snapshot: dict, merge_task_result_metadata) -> dict:
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        return {"ok": False, "reason": "task_not_found_after_process"}
    output_path = Path(result.output_path)
    if not output_path.exists():
        raise FileNotFoundError(f"处理结果文件未生成: {output_path}")
    merged_result_json = merge_task_result_metadata(task_snapshot["result_json"], result.result_json)
    task.status = TaskStatus.COMPLETED
    task.output_path = serialize_task_artifact_path(output_path) or result.output_path
    task.result_json = merged_result_json
    task.error_message = None
    task.updated_at = datetime.utcnow()
    db.flush()
    return {"ok": True, "task_id": task.id, "status": task.status.value}


def fail_processed_task(db, *, task_id: int, error: Exception, refund_task) -> dict:
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is not None:
        task.status = TaskStatus.FAILED
        task.error_message = str(error)
        task.updated_at = datetime.utcnow()
        refund_task(db, task)
        db.flush()
    return {"ok": False, "task_id": task_id, "error": str(error)}
