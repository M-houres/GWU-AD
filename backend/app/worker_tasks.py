from datetime import datetime
from functools import lru_cache
import logging
from pathlib import Path
import threading
import time

from celery import Celery
from celery.schedules import crontab
import redis
from redis import RedisError

from app.config import get_settings
from app.database import db_session
from app.models import CreditType, Task, TaskStatus, TaskType, User
from app.services.billing_rules_service import calc_task_cost_fen, resolve_task_points_per_char
from app.services.credit_service import change_credits
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.processing_engine import ProcessingEngine
from app.services.process_strategy_service import sanitize_user_result_json
from app.services.task_report_validation import validate_full_report_content
from app.services.worker_process_handler import (
    build_process_output_path,
    claim_process_task,
    fail_processed_task,
    finalize_processed_task,
    run_processing_engine,
)
from app.services.worker_preprocess_handler import run_preprocess_submission
from app.services.worker_task_support import (
    decrement_submission_counters,
    merge_task_result_metadata,
    processing_guard_keys,
    refund_task,
    release_processing_slot,
    try_acquire_processing_slot,
)
from app.services.worker_dispatch_runtime import (
    ensure_local_workers,
    get_local_task_queue,
    normalize_local_queue_name,
    resolve_local_worker_concurrency,
    run_task_locally,
    wait_for_local_tasks as wait_for_local_runtime_tasks,
)
from app.utils import count_billable_chars, extract_text_from_file

settings = get_settings()
logger = logging.getLogger("app.worker_tasks")

celery_app = Celery(
    "wuhongai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_track_started=True,
    timezone="Asia/Shanghai",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "tasks.preprocess_submission": {"queue": "submission"},
        "tasks.process_task": {"queue": "processing"},
        "tasks.cleanup_expired_task_artifacts": {"queue": "maintenance"},
    },
    beat_schedule={
        "cleanup-expired-task-artifacts-daily": {
            "task": "tasks.cleanup_expired_task_artifacts",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)

_worker_probe_lock = threading.Lock()
_worker_probe_state: dict[str, float | bool] = {"checked_at": 0.0, "ok": False}
_WORKER_PROBE_TTL_SECONDS = 2.0

@lru_cache(maxsize=1)
def _celery_broker_probe():
    broker_url = str(settings.celery_broker_url or "").strip()
    if not broker_url.startswith(("redis://", "rediss://")):
        return None
    return redis.Redis.from_url(
        broker_url,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
    )


def _celery_broker_available() -> bool:
    probe = _celery_broker_probe()
    if probe is None:
        return True
    try:
        probe.ping()
        return True
    except redis.RedisError:
        return False


def _celery_worker_available() -> bool:
    now = time.monotonic()
    with _worker_probe_lock:
        checked_at = float(_worker_probe_state.get("checked_at", 0.0) or 0.0)
        cached_ok = bool(_worker_probe_state.get("ok", False))
        if now - checked_at <= _WORKER_PROBE_TTL_SECONDS:
            return cached_ok

    available = False
    try:
        inspector = celery_app.control.inspect(timeout=0.4)
        replies = inspector.ping() or {}
        available = bool(replies)
    except Exception:
        available = False

    with _worker_probe_lock:
        _worker_probe_state["checked_at"] = now
        _worker_probe_state["ok"] = available
    return available


def _run_task_locally(task, args: tuple, kwargs: dict, task_name: str) -> None:
    run_task_locally(task, args, kwargs, task_name, logger=logger)


def _normalize_local_queue_name(queue_name: str | None) -> str:
    return normalize_local_queue_name(queue_name)


def _resolve_local_worker_concurrency(queue_name: str) -> int:
    return resolve_local_worker_concurrency(queue_name, settings=settings)


def _get_local_task_queue(queue_name: str):
    return get_local_task_queue(queue_name)


def _local_worker_loop(queue_name: str) -> None:
    from app.services.worker_dispatch_runtime import local_worker_loop

    local_worker_loop(queue_name, logger=logger)


def _ensure_local_workers(queue_name: str) -> None:
    ensure_local_workers(queue_name, settings=settings, logger=logger)


def wait_for_local_tasks(timeout_seconds: float = 5.0) -> bool:
    return wait_for_local_runtime_tasks(timeout_seconds)


def _merge_task_result_metadata(existing_result, new_result) -> dict:
    return merge_task_result_metadata(existing_result, new_result)


def dispatch_background_task(task, *args, queue: str | None = None, **kwargs) -> str:
    task_name = getattr(task, "name", getattr(task, "__name__", "unknown_task"))
    normalized_queue = _normalize_local_queue_name(queue)
    if not settings.is_prod and settings.celery_local_fallback_enabled:
        try:
            local_queue = _get_local_task_queue(normalized_queue)
            _ensure_local_workers(normalized_queue)
            local_queue.put((task, args, kwargs, task_name))
            return "local-queue"
        except Exception:
            logger.warning(
                "local_queue_dispatch_failed_run_inline",
                exc_info=True,
                extra={"task_name": task_name},
            )
            _run_task_locally(task, args, kwargs, task_name)
            return "inline"
    if _celery_broker_available():
        can_dispatch_celery = True
        if not settings.is_prod and settings.celery_local_fallback_enabled and not _celery_worker_available():
            can_dispatch_celery = False
            logger.warning("celery_worker_unavailable_fallback_local", extra={"task_name": task_name})

        if can_dispatch_celery:
            try:
                task.apply_async(args=args, kwargs=kwargs, queue=normalized_queue)
                return "celery"
            except Exception:
                logger.warning(
                    "celery_dispatch_failed_fallback_local",
                    exc_info=True,
                    extra={"task_name": task_name},
                )
    else:
        logger.warning("celery_broker_unavailable_fallback_local", extra={"task_name": task_name})

    if settings.is_prod:
        raise RuntimeError(f"celery broker unavailable for task {task_name}")
    if not settings.celery_local_fallback_enabled:
        raise RuntimeError(f"celery broker unavailable for task {task_name}")

    try:
        local_queue = _get_local_task_queue(normalized_queue)
        _ensure_local_workers(normalized_queue)
        local_queue.put((task, args, kwargs, task_name))
        return "local-queue"
    except Exception:
        logger.warning(
            "local_queue_dispatch_failed_run_inline",
            exc_info=True,
            extra={"task_name": task_name},
        )
        _run_task_locally(task, args, kwargs, task_name)
        return "inline"


def _refund_task(db, task: Task) -> None:
    refund_task(db, task)


def _validate_report_content(task_type: TaskType, path: Path) -> None:
    message = validate_full_report_content(task_type, path)
    if not message:
        return
    raise ValueError(message)


def _decrement_submission_counters(task: Task) -> None:
    decrement_submission_counters(task, settings=settings, logger=logger)


def _processing_guard_keys(task: Task) -> tuple[str, str]:
    return processing_guard_keys(task)


def _try_acquire_processing_slot(task: Task) -> bool:
    return try_acquire_processing_slot(task, settings=settings, logger=logger)


def _release_processing_slot(task: Task) -> None:
    release_processing_slot(task, settings=settings, logger=logger)


@celery_app.task(name="tasks.preprocess_submission")
def preprocess_submission_async(task_id: int) -> dict:
    with db_session() as db:
        try:
            result = run_preprocess_submission(
                db,
                task_id=task_id,
                validate_report_content=_validate_report_content,
                extract_text_from_file=extract_text_from_file,
                count_billable_chars=count_billable_chars,
                resolve_task_points_per_char=resolve_task_points_per_char,
                get_aigc_daily_quota=get_aigc_daily_quota,
                calc_task_cost_fen=calc_task_cost_fen,
                change_credits=change_credits,
            )
            if not result.get("ok"):
                return result
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return {"ok": False, "reason": "task_not_found"}
        except Exception as exc:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task is None:
                return {"ok": False, "reason": "task_not_found"}
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.updated_at = datetime.utcnow()
            db.flush()
            _decrement_submission_counters(task)
            return {"ok": False, "task_id": task.id, "error": str(exc)}

    dispatch_error: Exception | None = None
    try:
        dispatch_background_task(process_task_async, task_id, queue="processing")
    except Exception as exc:
        dispatch_error = exc
        logger.exception("task_process_dispatch_failed", extra={"task_id": task_id})

    with db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            _decrement_submission_counters(task)
            if dispatch_error is not None:
                task.status = TaskStatus.FAILED
                task.error_message = f"任务处理派发失败: {str(dispatch_error)[:180]}"
                task.updated_at = datetime.utcnow()
                _refund_task(db, task)
                db.flush()

    if dispatch_error is not None:
        return {"ok": False, "task_id": task_id, "error": str(dispatch_error)}
    return {"ok": True, "task_id": task_id, "status": TaskStatus.QUEUED.value}


@celery_app.task(name="tasks.process_task", bind=True)
def process_task_async(self, task_id: int) -> dict:
    with db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task is None:
            return {"ok": False, "reason": "task_not_found"}
        if not _try_acquire_processing_slot(task):
            countdown = max(int(settings.task_processing_retry_countdown_seconds or 1), 1)
            raise self.retry(countdown=countdown, max_retries=None)
        task_for_slot = Task(id=task.id, user_id=task.user_id)  # type: ignore[arg-type]
        try:
            claim_result = claim_process_task(db, task_id=task_id)
            if "snapshot" not in claim_result:
                return claim_result
            task_snapshot = claim_result["snapshot"]
            db.commit()

            output_path = build_process_output_path(task_snapshot, settings=settings)

            with db_session() as process_db:
                result = run_processing_engine(
                    process_db,
                    task_snapshot=task_snapshot,
                    output_path=output_path,
                    processing_engine_cls=ProcessingEngine,
                )

            with db_session() as db:
                return finalize_processed_task(
                    db,
                    task_id=task_id,
                    result=result,
                    task_snapshot=task_snapshot,
                    merge_task_result_metadata=_merge_task_result_metadata,
                )
        except Exception as exc:
            with db_session() as db:
                return fail_processed_task(db, task_id=task_id, error=exc, refund_task=_refund_task)
        finally:
            _release_processing_slot(task_for_slot)

@celery_app.task(name="tasks.cleanup_expired_task_artifacts")
def cleanup_expired_task_artifacts_async() -> dict:
    from app.main import cleanup_expired_task_artifacts

    cleanup_expired_task_artifacts()
    return {"ok": True}
