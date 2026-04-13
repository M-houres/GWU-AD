from datetime import datetime
from functools import lru_cache
import logging
from pathlib import Path
from queue import Queue
import threading
import time

from celery import Celery
import redis
from redis import RedisError

from app.config import get_settings
from app.database import db_session
from app.models import CreditType, Order, SystemConfig, Task, TaskStatus, TaskType, User
from app.services.credit_service import change_credits
from app.services.aigc_quota_service import get_aigc_daily_quota
from app.services.processing_engine import ProcessingEngine
from app.services.process_strategy_service import sanitize_user_result_json
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
        "tasks.grant_order_referral_rewards": {"queue": "maintenance"},
        "tasks.grant_register_rewards": {"queue": "maintenance"},
        "tasks.retry_referral_reward": {"queue": "maintenance"},
    },
)

_local_task_queue: Queue[tuple[object, tuple, dict, str]] = Queue()
_local_worker_lock = threading.Lock()
_local_task_queues: dict[str, Queue[tuple[object, tuple, dict, str]]] = {"default": _local_task_queue}
_local_worker_threads: dict[str, list[threading.Thread]] = {}

_TASK_RESULT_META_KEYS = ("paper_title", "authors")


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


def _run_task_locally(task, args: tuple, kwargs: dict, task_name: str) -> None:
    try:
        task(*args, **kwargs)
    except Exception:
        logger.exception("local_task_dispatch_failed", extra={"task_name": task_name})


def _normalize_local_queue_name(queue_name: str | None) -> str:
    normalized = str(queue_name or "default").strip().lower()
    if normalized in {"submission", "processing", "maintenance", "default"}:
        return normalized
    return "default"


def _resolve_local_worker_concurrency(queue_name: str) -> int:
    normalized = _normalize_local_queue_name(queue_name)
    if normalized == "submission":
        return max(int(settings.local_submission_worker_concurrency or 0), 1)
    if normalized == "processing":
        return max(int(settings.local_processing_worker_concurrency or 0), 1)
    return max(int(settings.local_maintenance_worker_concurrency or 0), 1)


def _get_local_task_queue(queue_name: str) -> Queue[tuple[object, tuple, dict, str]]:
    normalized = _normalize_local_queue_name(queue_name)
    queue = _local_task_queues.get(normalized)
    if queue is not None:
        return queue
    queue = Queue()
    _local_task_queues[normalized] = queue
    return queue


def _local_worker_loop(queue_name: str) -> None:
    local_queue = _get_local_task_queue(queue_name)
    while True:
        task, args, kwargs, task_name = local_queue.get()
        try:
            _run_task_locally(task, args, kwargs, task_name)
        finally:
            local_queue.task_done()


def _ensure_local_workers(queue_name: str) -> None:
    normalized = _normalize_local_queue_name(queue_name)
    with _local_worker_lock:
        _get_local_task_queue(normalized)
        existing = [thread for thread in _local_worker_threads.get(normalized, []) if thread.is_alive()]
        desired = _resolve_local_worker_concurrency(normalized)
        for index in range(len(existing), desired):
            thread = threading.Thread(
                target=_local_worker_loop,
                args=(normalized,),
                daemon=True,
                name=f"local-task-worker-{normalized}-{index + 1}",
            )
            thread.start()
            existing.append(thread)
        _local_worker_threads[normalized] = existing


def wait_for_local_tasks(timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    while time.monotonic() < deadline:
        unfinished = sum(queue.unfinished_tasks for queue in _local_task_queues.values())
        if unfinished == 0:
            return True
        time.sleep(0.01)
    return sum(queue.unfinished_tasks for queue in _local_task_queues.values()) == 0


def _merge_task_result_metadata(existing_result, new_result) -> dict:
    base = dict(new_result) if isinstance(new_result, dict) else {}
    if not isinstance(existing_result, dict):
        return base
    for key in _TASK_RESULT_META_KEYS:
        value = existing_result.get(key)
        if isinstance(value, str) and value.strip():
            base[key] = value.strip()
    return base


def dispatch_background_task(task, *args, queue: str | None = None, **kwargs) -> str:
    task_name = getattr(task, "name", getattr(task, "__name__", "unknown_task"))
    normalized_queue = _normalize_local_queue_name(queue)
    if _celery_broker_available():
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
    if task.refund_done:
        return
    user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
    if user is None:
        return
    change_credits(
        db,
        user,
        tx_type=CreditType.TASK_REFUND,
        delta=task.cost_credits,
        reason=f"任务失败退还积分(task_id={task.id})",
        related_id=f"task_refund:{task.id}",
        source=task.source,
    )
    task.refund_done = True
    db.flush()


def _resolve_task_rate(db, task_type: TaskType) -> int:
    from app.constants import TASK_RATES

    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == "billing")
        .first()
    )
    cfg = row.config_value if row and isinstance(row.config_value, dict) else {}
    key_map = {
        TaskType.AIGC_DETECT: "aigc_rate",
        TaskType.DEDUP: "dedup_rate",
        TaskType.REWRITE: "rewrite_rate",
    }
    key = key_map[task_type]
    value = cfg.get(key)
    if isinstance(value, int) and value > 0:
        return value
    return TASK_RATES[task_type]


def _report_is_full(task_type: TaskType, text: str) -> bool:
    content = " ".join((text or "").split()).lower()
    if not content:
        return False
    if task_type == TaskType.DEDUP:
        markers = ["全文", "总文字复制比", "去除引用复制比", "去除本人已发表文献复制比", "检测报告", "全文标明引文"]
        return sum(1 for marker in markers if marker in content) >= 2
    if task_type == TaskType.REWRITE:
        markers = ["aigc", "ai生成", "疑似ai", "检测报告", "全文", "总体风险", "高风险段落"]
        return sum(1 for marker in markers if marker in content) >= 2
    return False


def _validate_report_content(task_type: TaskType, path: Path) -> None:
    if task_type not in {TaskType.DEDUP, TaskType.REWRITE}:
        return
    report_text = extract_text_from_file(path)
    if _report_is_full(task_type, report_text):
        return
    if task_type == TaskType.DEDUP:
        raise ValueError("请上传全文查重报告")
    raise ValueError("请上传全文AIGC检测报告")


def _decrement_submission_counters(task: Task) -> None:
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        backlog_key = "task:submit:backlog"
        user_key = f"task:submit:inflight:user:{task.user_id}"
        backlog = int(redis_conn.get(backlog_key) or 0)
        user_inflight = int(redis_conn.get(user_key) or 0)
        if backlog > 0:
            redis_conn.decr(backlog_key)
        if user_inflight > 0:
            redis_conn.decr(user_key)
    except Exception:
        logger.warning("task_submit_counter_decrement_failed", exc_info=True, extra={"task_id": task.id})


def _processing_guard_keys(task: Task) -> tuple[str, str]:
    return ("task:processing:active", f"task:processing:user:{task.user_id}:active")


def _try_acquire_processing_slot(task: Task) -> bool:
    global_limit = max(int(settings.task_processing_global_concurrency or 0), 0)
    user_limit = max(int(settings.task_processing_user_concurrency or 0), 0)
    if global_limit <= 0 and user_limit <= 0:
        return True
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        global_key, user_key = _processing_guard_keys(task)
        global_count = int(redis_conn.get(global_key) or 0)
        user_count = int(redis_conn.get(user_key) or 0)
        if global_limit > 0 and global_count >= global_limit:
            return False
        if user_limit > 0 and user_count >= user_limit:
            return False
        redis_conn.incr(global_key)
        redis_conn.incr(user_key)
        redis_conn.expire(global_key, 3600)
        redis_conn.expire(user_key, 3600)
        return True
    except RedisError:
        logger.warning("task_processing_guard_redis_unavailable", exc_info=True, extra={"task_id": task.id})
        return True


def _release_processing_slot(task: Task) -> None:
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        global_key, user_key = _processing_guard_keys(task)
        global_count = int(redis_conn.get(global_key) or 0)
        user_count = int(redis_conn.get(user_key) or 0)
        if global_count > 0:
            redis_conn.decr(global_key)
        if user_count > 0:
            redis_conn.decr(user_key)
    except RedisError:
        logger.warning("task_processing_guard_release_failed", exc_info=True, extra={"task_id": task.id})


@celery_app.task(name="tasks.preprocess_submission")
def preprocess_submission_async(task_id: int) -> dict:
    with db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).with_for_update().first()
        if task is None:
            return {"ok": False, "reason": "task_not_found"}
        if task.status not in {TaskStatus.PREPROCESSING, TaskStatus.PENDING}:
            return {"ok": True, "task_id": task.id, "status": task.status.value}

        try:
            task.status = TaskStatus.PREPROCESSING
            db.flush()

            if task.report_path:
                _validate_report_content(task.task_type, Path(task.report_path))

            text = extract_text_from_file(Path(task.source_path))
            char_count = count_billable_chars(text)
            if char_count <= 0:
                raise ValueError("文档字符数为0，无法处理")

            rate = _resolve_task_rate(db, task.task_type)
            quota_before = (
                get_aigc_daily_quota(db, user_id=task.user_id, submitted_delta=-1)
                if task.task_type == TaskType.AIGC_DETECT
                else None
            )
            free_applied = bool(quota_before and quota_before["free_remaining_today"] > 0)
            cost = 0 if free_applied else rate * char_count
            user = db.query(User).filter(User.id == task.user_id).with_for_update().first()
            if user is None:
                raise ValueError("用户不存在")
            if user.credits < cost:
                raise ValueError("积分不足，请先充值")

            change_credits(
                db,
                user,
                tx_type=CreditType.TASK_CONSUME,
                delta=-cost,
                reason="AIGC每日免费额度抵扣" if free_applied else f"{task.task_type.value}任务提交扣费",
                related_id=f"task:{task.id}",
                source=task.source,
            )
            result_json = dict(task.result_json or {})
            result_json["billing"] = {
                "rate_per_char": rate,
                "free_applied": free_applied,
                "quota_before": quota_before,
            }
            task.char_count = char_count
            task.cost_credits = cost
            task.result_json = result_json
            task.status = TaskStatus.QUEUED
            task.updated_at = datetime.utcnow()
            db.flush()
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.updated_at = datetime.utcnow()
            db.flush()
            _decrement_submission_counters(task)
            return {"ok": False, "task_id": task.id, "error": str(exc)}

    dispatch_background_task(process_task_async, task_id, queue="processing")
    with db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            _decrement_submission_counters(task)
    return {"ok": True, "task_id": task_id, "status": TaskStatus.QUEUED.value}


@celery_app.task(name="tasks.process_task", bind=True)
def process_task_async(self, task_id: int) -> dict:
    with db_session() as db:
        task = db.query(Task).filter(Task.id == task_id).with_for_update().first()
        if task is None:
            return {"ok": False, "reason": "task_not_found"}
        if task.status == TaskStatus.COMPLETED:
            return {"ok": True, "task_id": task.id, "status": task.status.value}
        if task.status not in {TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING}:
            return {"ok": False, "task_id": task.id, "reason": f"invalid_status:{task.status.value}"}
        if not _try_acquire_processing_slot(task):
            countdown = max(int(settings.task_processing_retry_countdown_seconds or 1), 1)
            raise self.retry(countdown=countdown, max_retries=None)

        task.status = TaskStatus.RUNNING
        task.error_message = None
        db.flush()
        try:
            source_path = Path(task.source_path)
            output_dir = settings.output_dir / str(task.user_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_ext = ".pdf" if task.task_type.value == "aigc_detect" else source_path.suffix.lower()
            if not output_ext:
                output_ext = ".txt"
            output_path = output_dir / f"task_{task.id}_result{output_ext}"

            engine = ProcessingEngine(db)
            result = engine.process(
                task.task_type,
                task.platform,
                source_path,
                output_path,
                task_id=task.id,
                report_path=Path(task.report_path) if task.report_path else None,
                processing_mode=task.processing_mode,
            )
            merged_result_json = _merge_task_result_metadata(task.result_json, result.result_json)

            task.status = TaskStatus.COMPLETED
            task.output_path = result.output_path
            task.result_json = merged_result_json
            task.error_message = None
            task.updated_at = datetime.utcnow()
            db.flush()
            return {"ok": True, "task_id": task.id, "status": task.status.value}
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_message = str(exc)
            task.updated_at = datetime.utcnow()
            _refund_task(db, task)
            db.flush()
            return {"ok": False, "task_id": task.id, "error": str(exc)}
        finally:
            _release_processing_slot(task)


@celery_app.task(name="tasks.grant_order_referral_rewards", bind=True, max_retries=3)
def grant_order_referral_rewards_async(self, order_id: int) -> dict:
    return {"ok": False, "reason": "referral_module_disabled", "order_id": order_id}


@celery_app.task(name="tasks.grant_register_rewards", bind=True, max_retries=3)
def grant_register_rewards_async(self, relation_id: int) -> dict:
    return {"ok": False, "reason": "referral_module_disabled", "relation_id": relation_id}


@celery_app.task(name="tasks.retry_referral_reward")
def retry_referral_reward_async(reward_id: int) -> dict:
    return {"ok": False, "reason": "referral_module_disabled", "reward_id": reward_id}
