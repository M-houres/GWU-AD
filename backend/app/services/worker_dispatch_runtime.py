from queue import Queue
import threading
import time

_local_task_queue: Queue[tuple[object, tuple, dict, str]] = Queue()
_local_worker_lock = threading.Lock()
_local_task_queues: dict[str, Queue[tuple[object, tuple, dict, str]]] = {"default": _local_task_queue}
_local_worker_threads: dict[str, list[threading.Thread]] = {}


def run_task_locally(task, args: tuple, kwargs: dict, task_name: str, *, logger) -> None:
    try:
        task(*args, **kwargs)
    except Exception:
        logger.exception("local_task_dispatch_failed", extra={"task_name": task_name})


def normalize_local_queue_name(queue_name: str | None) -> str:
    normalized = str(queue_name or "default").strip().lower()
    if normalized in {"submission", "processing", "maintenance", "default"}:
        return normalized
    return "default"


def resolve_local_worker_concurrency(queue_name: str, *, settings) -> int:
    normalized = normalize_local_queue_name(queue_name)
    if normalized == "submission":
        return max(int(settings.local_submission_worker_concurrency or 0), 1)
    if normalized == "processing":
        return max(int(settings.local_processing_worker_concurrency or 0), 1)
    return max(int(settings.local_maintenance_worker_concurrency or 0), 1)


def get_local_task_queue(queue_name: str) -> Queue[tuple[object, tuple, dict, str]]:
    normalized = normalize_local_queue_name(queue_name)
    queue = _local_task_queues.get(normalized)
    if queue is not None:
        return queue
    queue = Queue()
    _local_task_queues[normalized] = queue
    return queue


def local_worker_loop(queue_name: str, *, logger) -> None:
    local_queue = get_local_task_queue(queue_name)
    while True:
        task, args, kwargs, task_name = local_queue.get()
        try:
            run_task_locally(task, args, kwargs, task_name, logger=logger)
        finally:
            local_queue.task_done()


def ensure_local_workers(queue_name: str, *, settings, logger) -> None:
    normalized = normalize_local_queue_name(queue_name)
    with _local_worker_lock:
        get_local_task_queue(normalized)
        existing = [thread for thread in _local_worker_threads.get(normalized, []) if thread.is_alive()]
        desired = resolve_local_worker_concurrency(normalized, settings=settings)
        for index in range(len(existing), desired):
            thread = threading.Thread(
                target=local_worker_loop,
                args=(normalized,),
                kwargs={"logger": logger},
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
