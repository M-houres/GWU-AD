import time

from app.config import get_settings
from app import worker_tasks
from app.worker_tasks import dispatch_background_task, wait_for_local_tasks


class DummyTask:
    name = "tests.dummy_task"

    def __init__(self, sink: list[int]) -> None:
        self.sink = sink

    def delay(self, *_args, **_kwargs) -> None:
        raise AssertionError("local fallback should not call celery delay")

    def __call__(self, value: int) -> None:
        time.sleep(0.01)
        self.sink.append(value)


def test_dispatch_background_task_falls_back_to_local_worker_pool(monkeypatch) -> None:
    settings = get_settings()
    old_env = settings.app_env
    old_processing_concurrency = settings.local_processing_worker_concurrency
    settings.app_env = "dev"
    settings.local_processing_worker_concurrency = 3

    try:
        sink: list[int] = []
        task = DummyTask(sink)
        monkeypatch.setattr("app.worker_tasks._celery_broker_available", lambda: False)

        assert wait_for_local_tasks(1.0)
        for item in range(6):
            mode = dispatch_background_task(task, item, queue="processing")
            assert mode == "local-queue"

        assert wait_for_local_tasks(2.0)
        assert sorted(sink) == list(range(6))
    finally:
        settings.app_env = old_env
        settings.local_processing_worker_concurrency = old_processing_concurrency


def test_cleanup_artifact_task_registered_in_beat_schedule() -> None:
    schedule = worker_tasks.celery_app.conf.beat_schedule
    assert "cleanup-expired-task-artifacts-daily" in schedule
    assert schedule["cleanup-expired-task-artifacts-daily"]["task"] == "tasks.cleanup_expired_task_artifacts"
