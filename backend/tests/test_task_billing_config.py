import io
import json
from io import BytesIO
import zipfile

from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import current_user
from app.main import app
from app.models import SystemConfig, Task, TaskStatus, User
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


def test_submit_task_uses_billing_config_rate(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800009991", nickname="rate-user", credits=10000)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="billing",
            config_value={"aigc_points_per_char": 1, "dedup_points_per_char": 5, "rewrite_points_per_char": 2},
        )
    )
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    settings = get_settings()
    monkeypatch.setattr(settings, "task_submit_user_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_ip_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_user_inflight_limit", 0)
    monkeypatch.setattr("app.worker_tasks.preprocess_submission_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        file_bytes = _make_docx_bytes("abcdefghij")
        resp = client.post(
            "/api/v1/tasks/submit",
            data={"task_type": "dedup", "platform": "cnki"},
            files={"paper": ("sample.docx", file_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["cost_credits"] == 50
        assert data["status"] == TaskStatus.PENDING.value

        row = db_session.get(Task, data["id"])
        assert row is not None
        assert row.cost_credits == 50
        assert row.status == TaskStatus.PENDING
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_dedup_requires_docx_source(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800009992", nickname="dedup-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="dedup")

    settings = get_settings()
    monkeypatch.setattr(settings, "task_submit_user_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_ip_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_user_inflight_limit", 0)
    monkeypatch.setattr("app.worker_tasks.preprocess_submission_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        file_bytes = BytesIO("abcdefghij".encode("utf-8"))
        resp = client.post(
            "/api/v1/tasks/submit",
            data={"task_type": "dedup", "platform": "cnki"},
            files={"paper": ("sample.txt", file_bytes, "text/plain")},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 4104
        assert "docx" in body["message"].lower()
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_rewrite_rejects_non_full_report(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800009993", nickname="rewrite-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="rewrite")

    settings = get_settings()
    monkeypatch.setattr(settings, "task_submit_user_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_ip_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_user_inflight_limit", 0)
    monkeypatch.setattr("app.worker_tasks.preprocess_submission_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        paper_bytes = _make_docx_bytes("这是一篇用于改写任务的论文正文，长度足够用于计费。")
        report_bytes = _make_docx_bytes("章节报告，仅包含部分片段，没有AIGC汇总结果。")
        resp = client.post(
            "/api/v1/tasks/submit",
            data={"task_type": "rewrite", "platform": "cnki"},
            files={
                "paper": ("paper.docx", paper_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "report": ("report.docx", report_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == 4115
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_rewrite_invalid_report_cleans_uploaded_files(
    client: TestClient,
    db_session: Session,
    monkeypatch,
    settings_override,
    tmp_path,
) -> None:
    user = User(phone="13800009994", nickname="rewrite-clean-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    _activate_slot(db_session, platform="cnki", function_type="rewrite")

    settings = get_settings()
    patched_upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(type(settings), "upload_dir", property(lambda self: patched_upload_dir))
    monkeypatch.setattr(settings, "task_submit_user_inflight_limit", 0)

    settings = get_settings()
    monkeypatch.setattr(settings, "task_submit_user_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_ip_1m_limit", 0)
    monkeypatch.setattr(settings, "task_submit_user_inflight_limit", 0)
    monkeypatch.setattr("app.worker_tasks.preprocess_submission_async.delay", lambda *_args, **_kwargs: None)
    app.dependency_overrides[current_user] = lambda: user
    try:
        paper_bytes = _make_docx_bytes("这是一篇用于清理无效报告测试的论文正文，长度足够用于计费。")
        report_bytes = _make_docx_bytes("章节报告，仅包含部分片段，没有AIGC汇总结果。")
        resp = client.post(
            "/api/v1/tasks/submit",
            data={"task_type": "rewrite", "platform": "cnki"},
            files={
                "paper": ("paper.docx", paper_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                "report": ("report.docx", report_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            },
        )
        assert resp.status_code == 422
        upload_user_dir = patched_upload_dir / str(user.id)
        assert not upload_user_dir.exists() or not any(upload_user_dir.iterdir())
    finally:
        app.dependency_overrides.pop(current_user, None)
