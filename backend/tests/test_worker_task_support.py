from types import SimpleNamespace

from app.models import CreditTransaction, CreditType, Task, TaskStatus, TaskType, User
from app.services import worker_task_support
from app.services.worker_task_support import (
    merge_task_result_metadata,
    processing_guard_keys,
    refund_task,
)


class _DummyRedis:
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

    def decr(self, key: str) -> int:
        value = int(self.values.get(key, 0)) - 1
        self.values[key] = value
        return value

    def expire(self, key: str, seconds: int) -> bool:
        self.expire_calls.append((key, seconds))
        return True


def test_merge_task_result_metadata_preserves_submission_fields() -> None:
    merged = merge_task_result_metadata(
        {"paper_title": "标题", "authors": "作者", "other": "x"},
        {"summary": "done", "paper_title": "会被覆盖"},
    )
    assert merged["paper_title"] == "标题"
    assert merged["authors"] == "作者"
    assert merged["summary"] == "done"


def test_refund_task_is_idempotent(db_session) -> None:
    user = User(phone="13800008901", nickname="refund-support-user", credits=800)
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.FAILED,
        source_filename="a.docx",
        source_path="/tmp/a.docx",
        cost_credits=200,
        refund_done=False,
    )
    db_session.add(task)
    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.TASK_CONSUME,
            delta=-200,
            balance_before=1000,
            balance_after=800,
            reason="dedup任务提交扣费",
            related_id=f"task:{task.id}",
            source="web",
        )
    )
    db_session.commit()

    refund_task(db_session, task)
    refund_task(db_session, task)
    db_session.refresh(user)
    assert user.credits == 1000
    rows = (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user.id,
            CreditTransaction.tx_type == CreditType.TASK_REFUND,
            CreditTransaction.related_id == f"task_refund:{task.id}",
        )
        .all()
    )
    assert len(rows) == 1


def test_processing_slot_helpers_use_expected_keys(monkeypatch) -> None:
    redis_conn = _DummyRedis()
    monkeypatch.setattr(worker_task_support.redis, "Redis", SimpleNamespace(from_url=lambda *_args, **_kwargs: redis_conn))
    task = Task(id=7, user_id=3)
    settings = SimpleNamespace(
        celery_broker_url="redis://127.0.0.1:6379/0",
        task_processing_global_concurrency=2,
        task_processing_user_concurrency=1,
    )
    logger = SimpleNamespace(warning=lambda *args, **kwargs: None)

    assert processing_guard_keys(task) == ("task:processing:active", "task:processing:user:3:active")
    assert worker_task_support.try_acquire_processing_slot(task, settings=settings, logger=logger) is True
    assert worker_task_support.try_acquire_processing_slot(task, settings=settings, logger=logger) is False
    worker_task_support.release_processing_slot(task, settings=settings, logger=logger)
