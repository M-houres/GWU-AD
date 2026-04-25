from app.models import Task, TaskStatus, TaskType, User
from app.services.worker_preprocess_handler import run_preprocess_submission


def test_worker_preprocess_handler_updates_task_and_billing(db_session, tmp_path) -> None:
    source_path = tmp_path / "source.docx"
    source_path.write_text("source", encoding="utf-8")
    user = User(phone="13800008911", nickname="preprocess-handler-user", credits=1000)
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.PREPROCESSING,
        source_filename="source.docx",
        source_path=str(source_path),
        result_json={"paper_title": "worker preprocess"},
    )
    db_session.add(task)
    db_session.flush()

    result = run_preprocess_submission(
        db_session,
        task_id=task.id,
        validate_report_content=lambda *_args, **_kwargs: None,
        extract_text_from_file=lambda *_args, **_kwargs: "有效正文",
        count_billable_chars=lambda *_args, **_kwargs: 120,
        resolve_task_points_per_char=lambda *_args, **_kwargs: 2,
        get_aigc_daily_quota=lambda *_args, **_kwargs: None,
        calc_task_cost_fen=lambda char_count, points: char_count * points,
        change_credits=lambda db, user, **kwargs: setattr(user, "credits", int(user.credits) + int(kwargs["delta"])),
    )

    assert result == {"ok": True, "task_id": task.id, "status": "queued"}
    assert task.status == TaskStatus.QUEUED
    assert task.char_count == 120
    assert task.cost_credits == 240
    assert task.result_json["billing"]["cost_points"] == 240


def test_worker_preprocess_handler_rejects_empty_text(db_session, tmp_path) -> None:
    source_path = tmp_path / "empty.docx"
    source_path.write_text("", encoding="utf-8")
    user = User(phone="13800008912", nickname="preprocess-empty-user", credits=1000)
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.PREPROCESSING,
        source_filename="empty.docx",
        source_path=str(source_path),
    )
    db_session.add(task)
    db_session.flush()

    try:
        run_preprocess_submission(
            db_session,
            task_id=task.id,
            validate_report_content=lambda *_args, **_kwargs: None,
            extract_text_from_file=lambda *_args, **_kwargs: "",
            count_billable_chars=lambda *_args, **_kwargs: 0,
            resolve_task_points_per_char=lambda *_args, **_kwargs: 2,
            get_aigc_daily_quota=lambda *_args, **_kwargs: None,
            calc_task_cost_fen=lambda char_count, points: char_count * points,
            change_credits=lambda *_args, **_kwargs: None,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "文档字符数为0" in str(exc)


def test_worker_preprocess_handler_resolves_relative_artifact_path(db_session, tmp_path, monkeypatch) -> None:
    source_root = tmp_path / "uploads"
    source_path = source_root / "5" / "source.docx"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("source", encoding="utf-8")
    user = User(phone="13800008913", nickname="preprocess-relative-user", credits=1000)
    db_session.add(user)
    db_session.flush()
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.PREPROCESSING,
        source_filename="source.docx",
        source_path="uploads/5/source.docx",
    )
    db_session.add(task)
    db_session.flush()

    from app.services import task_artifacts

    monkeypatch.setattr(
        task_artifacts,
        "settings",
        type("S", (), {"upload_dir": source_root, "output_dir": tmp_path / "output", "app_env": "prod"})(),
    )

    result = run_preprocess_submission(
        db_session,
        task_id=task.id,
        validate_report_content=lambda *_args, **_kwargs: None,
        extract_text_from_file=lambda path, *_args, **_kwargs: path.read_text(encoding="utf-8"),
        count_billable_chars=lambda text, *_args, **_kwargs: len(text),
        resolve_task_points_per_char=lambda *_args, **_kwargs: 1,
        get_aigc_daily_quota=lambda *_args, **_kwargs: None,
        calc_task_cost_fen=lambda char_count, points: char_count * points,
        change_credits=lambda db, user, **kwargs: setattr(user, "credits", int(user.credits) + int(kwargs["delta"])),
    )

    assert result == {"ok": True, "task_id": task.id, "status": "queued"}
