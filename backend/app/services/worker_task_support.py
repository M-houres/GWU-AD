import redis
from redis import RedisError

from app.models import CreditType, Task, User
from app.services.credit_service import change_credits
from app.services.partner_rebate_service import record_task_refund_rebate

TASK_RESULT_META_KEYS = ("paper_title", "authors")


def merge_task_result_metadata(existing_result, new_result) -> dict:
    base = dict(new_result) if isinstance(new_result, dict) else {}
    if not isinstance(existing_result, dict):
        return base
    for key in TASK_RESULT_META_KEYS:
        value = existing_result.get(key)
        if isinstance(value, str) and value.strip():
            base[key] = value.strip()
    return base


def refund_task(db, task: Task) -> None:
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
        reason=f"任务失败退还通用点数(task_id={task.id})",
        related_id=f"task_refund:{task.id}",
        source=task.source,
    )
    record_task_refund_rebate(db, task_id=task.id, operator="task_fail")
    task.refund_done = True
    db.flush()


def decrement_submission_counters(task: Task, *, settings, logger) -> None:
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        backlog_key = "task:submit:backlog"
        user_key = f"task:submit:inflight:user:{task.user_id}"
        new_backlog = redis_conn.decr(backlog_key)
        if new_backlog < 0:
            redis_conn.set(backlog_key, 0)
        new_user = redis_conn.decr(user_key)
        if new_user < 0:
            redis_conn.set(user_key, 0)
    except Exception:
        logger.warning("task_submit_counter_decrement_failed", exc_info=True, extra={"task_id": task.id})


def processing_guard_keys(task: Task) -> tuple[str, str]:
    return ("task:processing:active", f"task:processing:user:{task.user_id}:active")


def try_acquire_processing_slot(task: Task, *, settings, logger) -> bool:
    global_limit = max(int(settings.task_processing_global_concurrency or 0), 0)
    user_limit = max(int(settings.task_processing_user_concurrency or 0), 0)
    if global_limit <= 0 and user_limit <= 0:
        return True
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        global_key, user_key = processing_guard_keys(task)
        global_count = int(redis_conn.incr(global_key))
        if global_count == 1:
            redis_conn.expire(global_key, 3600)
        if global_limit > 0 and global_count > global_limit:
            redis_conn.decr(global_key)
            return False

        user_count = int(redis_conn.incr(user_key))
        if user_count == 1:
            redis_conn.expire(user_key, 3600)
        if user_limit > 0 and user_count > user_limit:
            if global_count > 0:
                redis_conn.decr(global_key)
            redis_conn.decr(user_key)
            return False
        return True
    except RedisError:
        logger.warning("task_processing_guard_redis_unavailable", exc_info=True, extra={"task_id": task.id})
        return True


def release_processing_slot(task: Task, *, settings, logger) -> None:
    try:
        redis_conn = redis.Redis.from_url(settings.celery_broker_url, decode_responses=True)
        global_key, user_key = processing_guard_keys(task)
        new_global = redis_conn.decr(global_key)
        if new_global < 0:
            redis_conn.set(global_key, 0)
        new_user = redis_conn.decr(user_key)
        if new_user < 0:
            redis_conn.set(user_key, 0)
    except RedisError:
        logger.warning("task_processing_guard_release_failed", exc_info=True, extra={"task_id": task.id})
