from contextlib import contextmanager
import io
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import zipfile

from docx import Document
from sqlalchemy.orm import Session

from app import worker_tasks
from app.config import get_settings
from app.deps import current_user
from app.main import app
from app.models import Task, TaskStatus, TaskType, User
from app.services.algo_package_service import install_algorithm_package


def _make_docx_bytes(text: str) -> BytesIO:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _build_package_zip(*, platform: str, function_type: str, name: str = "engine") -> bytes:
    manifest = {
        "name": name,
        "version": "1.0.0",
        "platform": platform,
        "function_type": function_type,
        "entry": "main.py",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr("main.py", "def process(text):\n    return {'text': str(text)}\n")
    return buf.getvalue()


def _activate_slot(db_session: Session, *, platform: str, function_type: str) -> None:
    install_algorithm_package(
        db_session,
        file_bytes=_build_package_zip(platform=platform, function_type=function_type, name=f"{function_type}_engine"),
        platform=platform,
        function_type=function_type,
        uploaded_by=1,
        activate_after_upload=True,
    )
    db_session.commit()


def test_submit_task_stores_metadata_and_unique_storage_paths(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800007771", nickname="submit-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    monkeypatch.setattr("app.worker_tasks.process_task_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "测试篇名",
                "authors": "张三;李四",
            },
            files={
                "paper": (
                    "sample.docx",
                    _make_docx_bytes("这是用于提交流程测试的正文内容。"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert resp.status_code == 200
        task = db_session.get(Task, resp.json()["data"]["id"])
        assert task is not None
        assert task.source_filename == "sample.docx"
        assert Path(task.source_path).name != "sample.docx"
        assert Path(task.source_path).name.endswith("_sample.docx")
        assert task.result_json["paper_title"] == "测试篇名"
        assert task.result_json["authors"] == "张三;李四"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_process_task_preserves_submission_metadata(
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "source.docx"
    _make_docx_bytes("这是一段用于结果元数据保留测试的文本。").seek(0)
    source_path.write_bytes(_make_docx_bytes("这是一段用于结果元数据保留测试的文本。").getvalue())

    user = User(phone="13800007772", nickname="process-user", credits=10000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.PENDING,
        source_filename="source.docx",
        source_path=str(source_path),
        char_count=30,
        cost_credits=60,
        result_json={"paper_title": "结果保留标题", "authors": "王五"},
    )
    db_session.add(task)
    db_session.commit()

    monkeypatch.setattr(
        worker_tasks.ProcessingEngine,
        "process",
        lambda *_args, **_kwargs: SimpleNamespace(
            output_path=str(tmp_path / "out.docx"),
            result_json={"summary": "done", "change_ratio": 18.5},
        ),
    )

    @contextmanager
    def _db_session_override():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr(worker_tasks, "db_session", _db_session_override)

    result = worker_tasks.process_task_async(task.id)
    assert result["ok"] is True

    db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED
    assert task.result_json["summary"] == "done"
    assert task.result_json["change_ratio"] == 18.5
    assert task.result_json["paper_title"] == "结果保留标题"
    assert task.result_json["authors"] == "王五"


def test_dispatch_background_task_falls_back_to_local_queue_in_prod(monkeypatch) -> None:
    settings = get_settings()
    old_env = settings.app_env

    class _DummyQueue:
        def __init__(self) -> None:
            self.items = []

        def put(self, value) -> None:
            self.items.append(value)

    class _DummyTask:
        name = "dummy-task"

        @staticmethod
        def delay(*_args, **_kwargs):
            raise AssertionError("delay should not be called when broker is unavailable")

    queue = _DummyQueue()
    settings.app_env = "prod"
    monkeypatch.setattr(worker_tasks, "_celery_broker_available", lambda: False)
    monkeypatch.setattr(worker_tasks, "_ensure_local_worker", lambda: None)
    monkeypatch.setattr(worker_tasks, "_local_task_queue", queue)
    try:
        mode = worker_tasks.dispatch_background_task(_DummyTask(), 1, foo="bar")
        assert mode == "local-queue"
        assert len(queue.items) == 1
    finally:
        settings.app_env = old_env
