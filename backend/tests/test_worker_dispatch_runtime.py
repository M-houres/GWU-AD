import time
from types import SimpleNamespace

from app.services import worker_dispatch_runtime
from app.services.worker_dispatch_runtime import (
    get_local_task_queue,
    normalize_local_queue_name,
    resolve_local_worker_concurrency,
    wait_for_local_tasks,
)


class _DummyLogger:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def exception(self, message: str, extra=None) -> None:
        self.errors.append(message)


def test_worker_dispatch_runtime_normalizes_queue_and_concurrency() -> None:
    settings = SimpleNamespace(
        local_submission_worker_concurrency=2,
        local_processing_worker_concurrency=3,
        local_maintenance_worker_concurrency=1,
    )
    assert normalize_local_queue_name("PROCESSING") == "processing"
    assert normalize_local_queue_name("unknown") == "default"
    assert resolve_local_worker_concurrency("submission", settings=settings) == 2
    assert resolve_local_worker_concurrency("processing", settings=settings) == 3
    assert resolve_local_worker_concurrency("default", settings=settings) == 1


def test_worker_dispatch_runtime_runs_local_queue_tasks() -> None:
    queue = get_local_task_queue("processing")
    logger = _DummyLogger()
    sink: list[int] = []

    worker_dispatch_runtime.ensure_local_workers(
        "processing",
        settings=SimpleNamespace(
            local_submission_worker_concurrency=1,
            local_processing_worker_concurrency=2,
            local_maintenance_worker_concurrency=1,
        ),
        logger=logger,
    )

    for value in range(4):
        queue.put((lambda current=value: (time.sleep(0.01), sink.append(current)), tuple(), {}, f"task-{value}"))

    assert wait_for_local_tasks(2.0) is True
    assert sorted(sink) == [0, 1, 2, 3]
    assert logger.errors == []
