from types import SimpleNamespace

from fastapi import Request

from app.exceptions import BizError
from app.models import TaskType
from app.services import task_submission_guards
from app.services.task_submission_guards import (
    acquire_submit_backlog,
    build_idempotency_key,
    check_submit_limits,
    decrement_submit_backlog,
    request_client_ip,
)


class DummyRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def incr(self, key: str) -> int:
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value

    def get(self, key: str):
        value = self.values.get(key)
        if value is None:
            return None
        return str(value)

    def expire(self, key: str, seconds: int) -> bool:
        self.expire_calls.append((key, seconds))
        return True

    def decr(self, key: str) -> int:
        value = int(self.values.get(key, 0)) - 1
        self.values[key] = value
        return value


def _build_request(*, headers: dict[str, str], host: str = "127.0.0.1") -> Request:
    return Request(
        scope={
            "type": "http",
            "method": "POST",
            "path": "/api/v1/tasks/submit",
            "headers": [(k.lower().encode("latin1"), v.encode("latin1")) for k, v in headers.items()],
            "client": (host, 12345),
        }
    )


def test_request_client_ip_prefers_forwarded_for() -> None:
    request = _build_request(headers={"X-Forwarded-For": "8.8.8.8, 1.1.1.1"}, host="127.0.0.1")
    assert request_client_ip(request) == "8.8.8.8"


def test_build_idempotency_key_hashes_and_caps_length() -> None:
    request = _build_request(headers={"X-Idempotency-Key": "x" * 220})

    key = build_idempotency_key(
        request,
        user_id=9,
        task_type=TaskType.DEDUP,
        platform="cnki",
        filename="sample.docx",
    )

    assert key is not None
    assert key.startswith("9:dedup:cnki:sha256:")
    assert len(key) <= 128


def test_check_submit_limits_raises_429_when_user_limit_exceeded(monkeypatch) -> None:
    redis_conn = DummyRedis()
    monkeypatch.setattr(task_submission_guards, "settings", SimpleNamespace(app_env="dev", task_submit_user_1m_limit=1, task_submit_ip_1m_limit=99))

    check_submit_limits(redis_conn, user_id=7, client_ip="10.0.0.1")
    try:
        check_submit_limits(redis_conn, user_id=7, client_ip="10.0.0.1")
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4116
        assert exc.http_status == 429


def test_acquire_and_decrement_submit_backlog_follow_limits(monkeypatch) -> None:
    redis_conn = DummyRedis()
    monkeypatch.setattr(
        task_submission_guards,
        "settings",
        SimpleNamespace(
            app_env="dev",
            is_prod=False,
            task_submit_user_inflight_limit=1,
            task_submit_queue_backlog_limit=10,
        ),
    )

    assert acquire_submit_backlog(redis_conn, user_id=3) is True
    try:
        acquire_submit_backlog(redis_conn, user_id=3)
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4117
        assert exc.http_status == 429

    decrement_submit_backlog(redis_conn, user_id=3)
    assert int(redis_conn.get("task:submit:backlog") or 0) >= 0
    assert int(redis_conn.get("task:submit:inflight:user:3") or 0) >= 0
