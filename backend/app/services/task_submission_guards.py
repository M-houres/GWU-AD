import hashlib
import logging

from fastapi import Request
from redis import RedisError

from app.config import get_settings
from app.exceptions import BizError
from app.models import TaskType

settings = get_settings()
logger = logging.getLogger("app.services.task_submission_guards")

IDEMPOTENCY_KEY_MAX_LEN = 128
IDEMPOTENCY_HEADER_MAX_LEN = 96
IDEMPOTENCY_HASH_HEX_LEN = 40


def request_client_ip(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def check_submit_limits(redis_conn, *, user_id: int, client_ip: str) -> None:
    if settings.app_env == "test":
        return
    checks = [
        (f"task:submit:user:{user_id}:1m", settings.task_submit_user_1m_limit, "提交过于频繁，请稍后再试"),
        (f"task:submit:ip:{client_ip}:1m", settings.task_submit_ip_1m_limit, "当前网络提交过于频繁，请稍后再试"),
    ]
    for key, limit, message in checks:
        if limit <= 0:
            continue
        current = redis_conn.incr(key)
        if current == 1:
            redis_conn.expire(key, 60)
        if current > limit:
            raise BizError(code=4116, message=message, http_status=429)


def submit_backlog_keys(user_id: int) -> tuple[str, str]:
    return ("task:submit:backlog", f"task:submit:inflight:user:{user_id}")


def decrement_submit_backlog(redis_conn, *, user_id: int) -> None:
    if settings.app_env == "test":
        return
    backlog_key, user_key = submit_backlog_keys(user_id)
    try:
        backlog = int(redis_conn.get(backlog_key) or 0)
        user_inflight = int(redis_conn.get(user_key) or 0)
        if backlog > 0:
            redis_conn.decr(backlog_key)
        if user_inflight > 0:
            redis_conn.decr(user_key)
    except Exception:
        logger.warning("task_submit_counter_decrement_failed", exc_info=True, extra={"user_id": user_id})


def acquire_submit_backlog(redis_conn, *, user_id: int) -> bool:
    if settings.app_env == "test":
        return False
    backlog_key, user_key = submit_backlog_keys(user_id)
    user_limit = max(int(settings.task_submit_user_inflight_limit or 0), 0)
    backlog_limit = max(int(settings.task_submit_queue_backlog_limit or 0), 0)
    try:
        backlog = int(redis_conn.incr(backlog_key))
        if backlog == 1:
            redis_conn.expire(backlog_key, 3600)
        if backlog_limit > 0 and backlog > backlog_limit:
            decrement_submit_backlog(redis_conn, user_id=user_id)
            raise BizError(code=4118, message="系统繁忙，请稍后再试", http_status=503)

        inflight = int(redis_conn.incr(user_key))
        if inflight == 1:
            redis_conn.expire(user_key, 3600)
        if user_limit > 0 and inflight > user_limit:
            decrement_submit_backlog(redis_conn, user_id=user_id)
            raise BizError(code=4117, message="当前处理中任务较多，请稍后再提交", http_status=429)
        return True
    except BizError:
        raise
    except RedisError as exc:
        if settings.is_prod:
            raise BizError(code=4118, message="系统繁忙，请稍后再试", http_status=503) from exc
        logger.warning("task_submit_backlog_acquire_failed", exc_info=True, extra={"user_id": user_id})
        return False


def increment_submit_backlog(redis_conn, *, user_id: int) -> None:
    acquired = acquire_submit_backlog(redis_conn, user_id=user_id)
    if not acquired:
        return
    _, user_key = submit_backlog_keys(user_id)
    if int(redis_conn.get(user_key) or 0) <= 0:
        redis_conn.expire(user_key, 3600)


def build_idempotency_key(
    request: Request,
    *,
    user_id: int,
    task_type: TaskType,
    platform: str,
    filename: str,
) -> str | None:
    raw = str(request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key") or "").strip()
    if not raw:
        return None
    normalized = raw[:IDEMPOTENCY_HEADER_MAX_LEN]
    seed = f"{user_id}:{task_type.value}:{platform}:{filename}:{normalized}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:IDEMPOTENCY_HASH_HEX_LEN]
    hashed_key = f"{user_id}:{task_type.value}:{platform}:sha256:{digest}"
    return hashed_key[:IDEMPOTENCY_KEY_MAX_LEN]
