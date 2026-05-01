from pathlib import Path
from types import SimpleNamespace

from app.models import Task, TaskStatus, TaskType, User
from app.services.worker_process_handler import (
    build_process_output_path,
    claim_process_task,
    fail_processed_task,
    finalize_processed_task,
    run_processing_engine,
)


def test_claim_process_task_marks_queued_task_running_and_returns_snapshot(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "queued.docx"
    report_path = tmp_path / "queued_report.docx"
    source_path.write_text("source", encoding="utf-8")
    report_path.write_text("report", encoding="utf-8")
    user = User(phone="13800008921", nickname="worker-process-user")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.QUEUED,
        source_filename="queued.docx",
        source_path=str(source_path),
        report_path=str(report_path),
        processing_mode="fast",
        result_json={"paper_title": "queued-paper"},
    )
    db_session.add(task)
    db_session.flush()

    result = claim_process_task(db_session, task_id=task.id)

    assert result["ok"] is True
    assert result["snapshot"]["id"] == task.id
    assert result["snapshot"]["source_path"] == str(source_path)
    assert result["snapshot"]["report_path"] == str(report_path)
    assert result["snapshot"]["processing_mode"] == "fast"
    db_session.refresh(task)
    assert task.status == TaskStatus.RUNNING
    assert task.error_message is None


def test_claim_process_task_rejects_invalid_status(db_session) -> None:
    user = User(phone="13800008922", nickname="worker-process-invalid")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.FAILED,
        source_filename="failed.docx",
        source_path="C:/tmp/failed.docx",
    )
    db_session.add(task)
    db_session.flush()

    result = claim_process_task(db_session, task_id=task.id)

    assert result == {"ok": False, "task_id": task.id, "reason": "invalid_status:failed"}


def test_build_process_output_path_uses_pdf_for_aigc(tmp_path: Path) -> None:
    settings = SimpleNamespace(output_dir=tmp_path / "output")

    path = build_process_output_path(
        {
            "id": 9,
            "user_id": 3,
            "task_type": TaskType.AIGC_DETECT,
            "source_filename": "输入论文.docx",
            "source_path": str(tmp_path / "input.docx"),
        },
        settings=settings,
    )

    assert path.parent == tmp_path / "output" / "3" / "9"
    assert path.suffix.lower() == ".pdf"
    assert path.name.endswith(".pdf")


def test_run_processing_engine_passes_snapshot_fields(db_session, tmp_path: Path) -> None:
    source_path = tmp_path / "source.docx"
    report_path = tmp_path / "report.docx"
    output_path = tmp_path / "output.docx"
    source_path.write_text("source", encoding="utf-8")
    report_path.write_text("report", encoding="utf-8")
    calls: dict[str, object] = {}

    class FakeEngine:
        def __init__(self, db) -> None:
            calls["db"] = db

        def process(self, task_type, platform, source, output, **kwargs):
            calls["task_type"] = task_type
            calls["platform"] = platform
            calls["source"] = source
            calls["output"] = output
            calls["kwargs"] = kwargs
            return SimpleNamespace(output_path=str(output), result_json={"score": 0.5})

    result = run_processing_engine(
        db_session,
        task_snapshot={
            "id": 11,
            "task_type": TaskType.DEDUP,
            "platform": "cnki",
            "source_path": str(source_path),
            "report_path": str(report_path),
            "processing_mode": "deep",
        },
        output_path=output_path,
        processing_engine_cls=FakeEngine,
    )

    assert result.output_path == str(output_path)
    assert calls["db"] is db_session
    assert calls["task_type"] == TaskType.DEDUP
    assert calls["platform"] == "cnki"
    assert calls["source"] == source_path
    assert calls["output"] == output_path
    assert calls["kwargs"] == {
        "task_id": 11,
        "report_path": report_path,
        "processing_mode": "deep",
    }


def test_finalize_processed_task_merges_metadata_and_completes(db_session) -> None:
    user = User(phone="13800008923", nickname="worker-process-finalize")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.RUNNING,
        source_filename="done.docx",
        source_path="C:/tmp/done.docx",
        result_json={"paper_title": "before"},
    )
    db_session.add(task)
    db_session.flush()
    output_path = Path("C:/tmp/result.docx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("result", encoding="utf-8")

    merged = finalize_processed_task(
        db_session,
        task_id=task.id,
        result=SimpleNamespace(output_path=str(output_path), result_json={"score": 0.92}),
        task_snapshot={"result_json": {"paper_title": "before"}},
        merge_task_result_metadata=lambda existing, new: {**existing, **new, "merged": True},
    )

    assert merged == {"ok": True, "task_id": task.id, "status": "completed"}
    assert task.status == TaskStatus.COMPLETED
    assert task.output_path == str(output_path)
    assert task.result_json == {"paper_title": "before", "score": 0.92, "merged": True}
    assert task.error_message is None


def test_finalize_processed_task_serializes_output_path_under_output_root(db_session, tmp_path, monkeypatch) -> None:
    from app.services import task_artifacts

    output_root = tmp_path / "output"
    monkeypatch.setattr(
        task_artifacts,
        "settings",
        SimpleNamespace(upload_dir=tmp_path / "uploads", output_dir=output_root, app_env="prod"),
    )
    user = User(phone="13800008926", nickname="worker-process-output-relative")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.RUNNING,
        source_filename="done.docx",
        source_path="uploads/1/done.docx",
        result_json={"paper_title": "before"},
    )
    db_session.add(task)
    db_session.flush()
    output_path = output_root / str(user.id) / str(task.id) / "改写+done.docx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("result", encoding="utf-8")

    merged = finalize_processed_task(
        db_session,
        task_id=task.id,
        result=SimpleNamespace(output_path=str(output_path), result_json={"score": 0.92}),
        task_snapshot={"result_json": {"paper_title": "before"}},
        merge_task_result_metadata=lambda existing, new: {**existing, **new, "merged": True},
    )

    assert merged == {"ok": True, "task_id": task.id, "status": "completed"}
    assert task.output_path == f"output/{user.id}/{task.id}/改写+done.docx"


def test_fail_processed_task_marks_failed_and_refunds(db_session) -> None:
    user = User(phone="13800008924", nickname="worker-process-fail")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.RUNNING,
        source_filename="fail.docx",
        source_path="C:/tmp/fail.docx",
    )
    db_session.add(task)
    db_session.flush()
    refunded: list[int] = []

    result = fail_processed_task(
        db_session,
        task_id=task.id,
        error=RuntimeError("engine crashed"),
        refund_task=lambda db, failed_task: refunded.append(failed_task.id),
    )

    assert result == {"ok": False, "task_id": task.id, "error": "engine crashed"}
    assert task.status == TaskStatus.FAILED
    assert task.error_message == "engine crashed"
    assert refunded == [task.id]


def test_process_task_async_releases_slot_when_claim_returns_terminal_status(db_session, monkeypatch) -> None:
    from contextlib import contextmanager

    from app import worker_tasks

    user = User(phone="13800008925", nickname="worker-process-slot-release")
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.COMPLETED,
        source_filename="done.docx",
        source_path="C:/tmp/done.docx",
    )
    db_session.add(task)
    db_session.commit()
    released: list[tuple[int | None, int | None]] = []

    @contextmanager
    def _db_session_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(worker_tasks, "db_session", _db_session_override)
    monkeypatch.setattr(worker_tasks, "_try_acquire_processing_slot", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        worker_tasks,
        "_release_processing_slot",
        lambda task_for_slot: released.append((task_for_slot.id, task_for_slot.user_id)),
    )

    result = worker_tasks.process_task_async(task.id)

    assert result == {"ok": True, "task_id": task.id, "status": "completed"}
    assert released == [(task.id, user.id)]
