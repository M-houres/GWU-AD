from pathlib import Path

from app.exceptions import BizError
from app.models import Task, TaskStatus, TaskType, User
from app.services.task_query_actions import (
    delete_user_task,
    get_user_task_download_path,
    list_user_tasks,
)


def test_list_user_tasks_filters_and_paginates(db_session) -> None:
    user = User(phone="13800008895", nickname="query-user", credits=1000)
    other = User(phone="13800008896", nickname="other-user", credits=1000)
    db_session.add_all([user, other])
    db_session.flush()

    rows = [
        Task(
            user_id=user.id,
            task_type=TaskType.DEDUP,
            platform="cnki",
            status=TaskStatus.COMPLETED,
            source_filename="a.docx",
            source_path="/tmp/a.docx",
            char_count=100,
            cost_credits=20,
        ),
        Task(
            user_id=user.id,
            task_type=TaskType.REWRITE,
            platform="vip",
            status=TaskStatus.FAILED,
            source_filename="b.docx",
            source_path="/tmp/b.docx",
            char_count=200,
            cost_credits=40,
        ),
        Task(
            user_id=other.id,
            task_type=TaskType.DEDUP,
            platform="cnki",
            status=TaskStatus.COMPLETED,
            source_filename="other.docx",
            source_path="/tmp/other.docx",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()

    payload = list_user_tasks(
        db_session,
        user_id=user.id,
        page=1,
        page_size=20,
        task_type="dedup",
        platform="cnki",
        status="completed",
    )

    assert payload["pagination"]["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source_filename"] == "a.docx"


def test_list_user_tasks_rejects_bad_filter_values(db_session) -> None:
    try:
        list_user_tasks(db_session, user_id=1, page=1, page_size=20, task_type="bad")
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4101

    try:
        list_user_tasks(db_session, user_id=1, page=1, page_size=20, status="bad")
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4110

    try:
        list_user_tasks(db_session, user_id=1, page=1, page_size=20, start_date="2026/01/01")
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4111


def test_get_user_task_download_path_validates_status_and_file(db_session, tmp_path: Path) -> None:
    output_path = tmp_path / "result.txt"
    output_path.write_text("result", encoding="utf-8")
    user = User(phone="13800008897", nickname="download-query-user", credits=1000)
    db_session.add(user)
    db_session.flush()
    completed = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.COMPLETED,
        source_filename="done.docx",
        source_path="/tmp/done.docx",
        output_path=str(output_path),
    )
    pending = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.PENDING,
        source_filename="pending.docx",
        source_path="/tmp/pending.docx",
    )
    db_session.add_all([completed, pending])
    db_session.commit()

    assert get_user_task_download_path(db_session, user_id=user.id, task_id=completed.id) == output_path
    try:
        get_user_task_download_path(db_session, user_id=user.id, task_id=pending.id)
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4108

    output_path.unlink()
    try:
        get_user_task_download_path(db_session, user_id=user.id, task_id=completed.id)
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4109


def test_delete_user_task_rejects_running_and_removes_artifacts(db_session, tmp_path: Path, monkeypatch) -> None:
    user = User(phone="13800008898", nickname="delete-query-user", credits=1000)
    db_session.add(user)
    db_session.flush()
    source_path = tmp_path / "source.docx"
    report_path = tmp_path / "report.pdf"
    output_path = tmp_path / "output.docx"
    for path in (source_path, report_path, output_path):
        path.write_text("x", encoding="utf-8")
    running = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.RUNNING,
        source_filename="running.docx",
        source_path=str(source_path),
    )
    failed = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.FAILED,
        source_filename="failed.docx",
        source_path=str(source_path),
        report_path=str(report_path),
        output_path=str(output_path),
    )
    db_session.add_all([running, failed])
    db_session.commit()

    try:
        delete_user_task(db_session, user_id=user.id, task_id=running.id)
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4113

    monkeypatch.setattr("app.services.task_query_actions.safe_remove_task_artifact", lambda raw_path: Path(raw_path).unlink(missing_ok=True))
    payload = delete_user_task(db_session, user_id=user.id, task_id=failed.id)
    assert payload == {"task_id": failed.id, "deleted": True}
    assert db_session.get(Task, failed.id) is None
    assert not source_path.exists()
    assert not report_path.exists()
    assert not output_path.exists()
