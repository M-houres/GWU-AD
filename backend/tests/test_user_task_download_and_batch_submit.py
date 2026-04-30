from contextlib import contextmanager
import io
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote
import zipfile

from docx import Document
from sqlalchemy.orm import Session

from app import worker_tasks
from app.config import get_settings
from app.deps import current_user
from app.main import app
from app.models import Task, TaskStatus, TaskType, User


def _make_docx_bytes(text: str) -> BytesIO:
    doc = Document()
    doc.add_paragraph(text)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def test_user_can_download_completed_task_result(client, db_session: Session, tmp_path: Path) -> None:
    output_path = tmp_path / "user_task_result.txt"
    output_path.write_text("user download result", encoding="utf-8")

    user = User(phone="13800006660", nickname="download-user", credits=1000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.COMPLETED,
        source_filename="paper.docx",
        source_path=str(tmp_path / "paper.docx"),
        output_path=str(output_path),
        char_count=200,
        cost_credits=200,
        result_json={"paper_title": "下载测试"},
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get(f"/api/v1/tasks/{task.id}/download")
        assert resp.status_code == 200
        assert resp.content == b"user download result"
        assert "改写+paper.txt" in unquote(resp.headers.get("content-disposition", ""))
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_user_can_download_aigc_pdf_with_pdf_content_type(client, db_session: Session, tmp_path: Path) -> None:
    output_path = tmp_path / "user_aigc_report.pdf"
    output_path.write_bytes(b"%PDF-1.4\n%mock pdf\n")

    user = User(phone="13800006662", nickname="download-aigc-user", credits=1000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.AIGC_DETECT,
        platform="cnki",
        status=TaskStatus.COMPLETED,
        source_filename="paper.docx",
        source_path=str(tmp_path / "paper.docx"),
        output_path=str(output_path),
        char_count=320,
        cost_credits=200,
        result_json={"paper_title": "AIGC下载测试"},
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get(f"/api/v1/tasks/{task.id}/download")
        assert resp.status_code == 200
        assert resp.content == b"%PDF-1.4\n%mock pdf\n"
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "paper_AIGC检测报告.pdf" in unquote(resp.headers.get("content-disposition", ""))
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_task_detail_hides_output_path_and_exposes_download_ready(client, db_session: Session, tmp_path: Path) -> None:
    output_path = tmp_path / "hidden_result.txt"
    output_path.write_text("hidden result", encoding="utf-8")

    user = User(phone="13800006663", nickname="detail-user", credits=1000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.COMPLETED,
        source_filename="paper.docx",
        source_path=str(tmp_path / "paper.docx"),
        output_path=str(output_path),
        char_count=120,
        cost_credits=20,
        result_json={"paper_title": "详情测试"},
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get(f"/api/v1/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "output_path" not in data
        assert data["download_ready"] is True
        assert data["refund_done"] is False
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_delete_task_removes_task_artifacts(client, db_session: Session) -> None:
    settings = get_settings()
    user = User(phone="13800006664", nickname="delete-user", credits=1000)
    db_session.add(user)
    db_session.flush()

    upload_dir = settings.upload_dir / str(user.id)
    output_dir = settings.output_dir / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = upload_dir / "source_delete.docx"
    report_path = upload_dir / "report_delete.pdf"
    output_path = output_dir / "result_delete.docx"
    source_path.write_text("source", encoding="utf-8")
    report_path.write_text("report", encoding="utf-8")
    output_path.write_text("result", encoding="utf-8")

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.FAILED,
        source_filename="source_delete.docx",
        source_path=str(source_path),
        report_path=str(report_path),
        output_path=str(output_path),
        char_count=120,
        cost_credits=20,
        result_json={"paper_title": "删除测试"},
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.delete(f"/api/v1/tasks/{task.id}")
        assert resp.status_code == 200
        assert not source_path.exists()
        assert not report_path.exists()
        assert not output_path.exists()
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_multiple_quick_submissions_can_all_process_and_download(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800006661", nickname="batch-user", credits=20000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    monkeypatch.setattr("app.worker_tasks.dispatch_background_task", lambda *_args, **_kwargs: "test-noop")

    app.dependency_overrides[current_user] = lambda: user
    try:
        task_ids: list[int] = []
        for idx in range(3):
            resp = client.post(
                "/api/v1/tasks/submit",
                data={
                    "task_type": "dedup",
                    "platform": "cnki",
                    "paper_title": "短时间连续提交测试",
                    "authors": "测试作者",
                },
                files={
                    "paper": (
                        "same_name.docx",
                        _make_docx_bytes(f"第{idx + 1}篇：用于验证短时间连续提交的正文内容。"),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
            assert resp.status_code == 200
            task_ids.append(resp.json()["data"]["id"])

        assert len(set(task_ids)) == 3

        rows = db_session.query(Task).filter(Task.id.in_(task_ids)).order_by(Task.id.asc()).all()
        assert len(rows) == 3
        assert all(row.status == TaskStatus.PENDING for row in rows)
        assert len({row.source_path for row in rows}) == 3
        assert all(Path(row.source_path).name.endswith("_same_name.docx") for row in rows)

        @contextmanager
        def _db_session_override():
            try:
                yield db_session
                db_session.commit()
            except Exception:
                db_session.rollback()
                raise

        monkeypatch.setattr(worker_tasks, "db_session", _db_session_override)

        for task_id in task_ids:
            result = worker_tasks.process_task_async(task_id)
            assert result["ok"] is True

        for task_id in task_ids:
            row = db_session.get(Task, task_id)
            assert row is not None
            assert row.status == TaskStatus.COMPLETED
            assert row.output_path
            assert Path(row.output_path).exists()

            download_resp = client.get(f"/api/v1/tasks/{task_id}/download")
            assert download_resp.status_code == 200
            assert len(download_resp.content) > 0
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_submit_task_rejects_generic_zip_renamed_as_docx(
    client,
    db_session: Session,
    monkeypatch,
    settings_override,
) -> None:
    user = User(phone="13800006665", nickname="magic-user", credits=10000)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    monkeypatch.setattr("app.worker_tasks.dispatch_background_task", lambda *_args, **_kwargs: "test-noop")

    fake_zip = io.BytesIO()
    with zipfile.ZipFile(fake_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("hello.txt", "not a docx")

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.post(
            "/api/v1/tasks/submit",
            data={
                "task_type": "dedup",
                "platform": "cnki",
                "paper_title": "伪装文件测试",
                "authors": "测试作者",
            },
            files={
                "paper": (
                    "fake.docx",
                    fake_zip.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == 4105
    finally:
        app.dependency_overrides.pop(current_user, None)
