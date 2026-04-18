from contextlib import contextmanager
import io
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import zipfile

from docx import Document
import pytest
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
        payload = resp.json()["data"]
        assert payload["task_type"] == "dedup"
        assert payload["source_filename"] == "sample.docx"
        assert payload["char_count"] == task.char_count
        assert payload["balance_after"] == user.credits
        assert payload["idempotent"] is False
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_recover_by_idempotency_key(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800007773", nickname="recover-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    monkeypatch.setattr("app.worker_tasks.process_task_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        idem = "recover-chain-001"
        submit_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "幂等找回测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "recover.docx",
                    _make_docx_bytes("这是用于幂等找回测试的正文。"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-Idempotency-Key": idem},
        )
        assert submit_resp.status_code == 200
        task_id = int(submit_resp.json()["data"]["id"])

        recover_resp = client.post(
            "/api/v1/tasks/submit/recover",
            json={
                "task_type": "dedup",
                "platform": "cnki",
                "source_filename": "recover.docx",
            },
            headers={"X-Idempotency-Key": idem},
        )
        assert recover_resp.status_code == 200
        data = recover_resp.json()["data"]
        assert int(data["id"]) == task_id
        assert data["task_type"] == "dedup"
        assert data["platform"] == "cnki"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_recover_with_long_idempotency_key_does_not_overflow_column(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800007774", nickname="recover-long-idem-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    monkeypatch.setattr("app.worker_tasks.process_task_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        idem = "recover-chain-overflow-" + ("x" * 220)
        source_filename = "recover_" + ("x" * 48) + ".docx"
        submit_resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "幂等超长键测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    source_filename,
                    _make_docx_bytes("这是用于幂等超长键回归测试的正文。"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            headers={"X-Idempotency-Key": idem},
        )
        assert submit_resp.status_code == 200
        task_id = int(submit_resp.json()["data"]["id"])
        task = db_session.get(Task, task_id)
        assert task is not None
        assert task.idempotency_key is not None
        assert len(task.idempotency_key) <= 128

        recover_resp = client.post(
            "/api/v1/tasks/submit/recover",
            json={
                "task_type": "dedup",
                "platform": "cnki",
                "source_filename": source_filename,
            },
            headers={"X-Idempotency-Key": idem},
        )
        assert recover_resp.status_code == 200
        assert int(recover_resp.json()["data"]["id"]) == task_id
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_task_still_returns_success_when_dispatch_fails_after_commit(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    settings = get_settings()
    old_env = settings.app_env
    user = User(phone="13800007770", nickname="dispatch-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    monkeypatch.setattr("app.worker_tasks.dispatch_background_task", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("queue down")))
    app.dependency_overrides[current_user] = lambda: user
    try:
        settings.app_env = "dev"
        resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "派发异常测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "dispatch.docx",
                    _make_docx_bytes("这是用于验证派发失败后仍返回成功的正文内容。"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert resp.status_code == 200
        payload = resp.json()["data"]
        assert payload["dispatch_mode"] == "failed"
        assert payload["status"] == "failed"
        assert payload["balance_after"] == 10000
        task = db_session.get(Task, payload["id"])
        assert task is not None
        assert task.status == TaskStatus.FAILED
        assert task.result_json["paper_title"] == "派发异常测试"
    finally:
        settings.app_env = old_env
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


def test_preprocess_marks_failed_and_refunds_when_process_dispatch_fails(
    db_session: Session,
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "dispatch_fail_source.docx"
    source_path.write_bytes(_make_docx_bytes("这是一段用于二段派发失败兜底测试的文本。").getvalue())

    user = User(phone="13800007775", nickname="preprocess-dispatch-user", credits=10000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.PREPROCESSING,
        source_filename="dispatch_fail_source.docx",
        source_path=str(source_path),
        char_count=0,
        cost_credits=0,
        result_json={"paper_title": "派发失败回滚测试", "authors": "测试作者"},
    )
    db_session.add(task)
    db_session.commit()

    starting_credits = int(user.credits)

    monkeypatch.setattr(worker_tasks, "extract_text_from_file", lambda *_args, **_kwargs: "有效正文内容")
    monkeypatch.setattr(worker_tasks, "count_billable_chars", lambda *_args, **_kwargs: 100)
    monkeypatch.setattr(worker_tasks, "resolve_task_points_per_char", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(worker_tasks, "_decrement_submission_counters", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        worker_tasks,
        "dispatch_background_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("processing queue down")),
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

    result = worker_tasks.preprocess_submission_async(task.id)

    assert result["ok"] is False
    assert "processing queue down" in str(result.get("error"))
    db_session.refresh(task)
    db_session.refresh(user)
    assert task.status == TaskStatus.FAILED
    assert "任务处理派发失败" in str(task.error_message or "")
    assert task.cost_credits == 200
    assert task.refund_done is True
    assert int(user.credits) == starting_credits


def test_dispatch_background_task_rejects_local_fallback_in_prod(monkeypatch) -> None:
    settings = get_settings()
    old_env = settings.app_env
    old_local_fallback = settings.celery_local_fallback_enabled

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

    settings.app_env = "prod"
    settings.celery_local_fallback_enabled = True
    monkeypatch.setattr(worker_tasks, "_celery_broker_available", lambda: False)
    monkeypatch.setattr(worker_tasks, "_ensure_local_workers", lambda *_args, **_kwargs: None)
    try:
        with pytest.raises(RuntimeError) as exc_info:
            worker_tasks.dispatch_background_task(_DummyTask(), 1, foo="bar")
        assert "celery broker unavailable" in str(exc_info.value)
    finally:
        settings.app_env = old_env
        settings.celery_local_fallback_enabled = old_local_fallback


def test_dispatch_background_task_falls_back_local_when_worker_unavailable_in_dev(monkeypatch) -> None:
    settings = get_settings()
    old_env = settings.app_env
    old_local_fallback = settings.celery_local_fallback_enabled

    class _DummyQueue:
        def __init__(self) -> None:
            self.items = []

        def put(self, value) -> None:
            self.items.append(value)

    class _DummyTask:
        name = "dummy-task"

        @staticmethod
        def apply_async(*_args, **_kwargs):
            raise AssertionError("apply_async should not be called when worker is unavailable in dev fallback mode")

    queue = _DummyQueue()
    settings.app_env = "dev"
    settings.celery_local_fallback_enabled = True
    monkeypatch.setattr(worker_tasks, "_celery_broker_available", lambda: True)
    monkeypatch.setattr(worker_tasks, "_celery_worker_available", lambda: False)
    monkeypatch.setattr(worker_tasks, "_get_local_task_queue", lambda *_args, **_kwargs: queue)
    monkeypatch.setattr(worker_tasks, "_ensure_local_workers", lambda *_args, **_kwargs: None)
    try:
        mode = worker_tasks.dispatch_background_task(_DummyTask(), 1, queue="processing", foo="bar")
        assert mode == "local-queue"
        assert len(queue.items) == 1
        _, args, kwargs, task_name = queue.items[0]
        assert args == (1,)
        assert kwargs["foo"] == "bar"
        assert task_name == "dummy-task"
    finally:
        settings.app_env = old_env
        settings.celery_local_fallback_enabled = old_local_fallback
