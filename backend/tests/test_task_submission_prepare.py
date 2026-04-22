from pathlib import Path

from app.exceptions import BizError
from app.models import CreditTransaction, CreditType, Task, TaskStatus, TaskType, User
from app.services import task_submission_prepare
from app.services.task_submission_prepare import initial_billing_payload, prepare_task_for_processing


def test_prepare_task_for_processing_charges_and_writes_billing(db_session, tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "source.docx"
    source_path.write_text("source", encoding="utf-8")
    user = User(phone="13800008891", nickname="prepare-user", credits=1000)
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
        result_json={"paper_title": "预处理测试"},
    )
    db_session.add(task)
    db_session.flush()

    monkeypatch.setattr(task_submission_prepare, "extract_text_from_file", lambda *_args, **_kwargs: "有效正文")
    monkeypatch.setattr(task_submission_prepare, "count_billable_chars", lambda *_args, **_kwargs: 120)
    monkeypatch.setattr(task_submission_prepare, "resolve_task_points_per_char", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(task_submission_prepare, "calc_task_cost_fen", lambda char_count, points: char_count * points)

    payload = prepare_task_for_processing(db_session, task=task)

    assert payload["points_per_char"] == 2.0
    assert payload["free_applied"] is False
    assert payload["cost_fen"] == 240
    assert task.status == TaskStatus.PENDING
    assert task.char_count == 120
    assert task.cost_credits == 240
    assert task.result_json["paper_title"] == "预处理测试"
    assert task.result_json["billing"]["cost_points"] == 240

    db_session.refresh(user)
    assert user.credits == 760
    tx = db_session.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).one()
    assert tx.tx_type == CreditType.TASK_CONSUME
    assert tx.delta == -240
    assert tx.related_id == f"task:{task.id}"


def test_prepare_task_for_processing_rejects_empty_source(db_session, tmp_path: Path, monkeypatch) -> None:
    source_path = tmp_path / "empty.docx"
    source_path.write_text("", encoding="utf-8")
    user = User(phone="13800008892", nickname="empty-user", credits=1000)
    db_session.add(user)
    db_session.flush()

    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        status=TaskStatus.PREPROCESSING,
        source_filename="empty.docx",
        source_path=str(source_path),
    )
    db_session.add(task)
    db_session.flush()

    monkeypatch.setattr(task_submission_prepare, "extract_text_from_file", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(task_submission_prepare, "count_billable_chars", lambda *_args, **_kwargs: 0)

    try:
        prepare_task_for_processing(db_session, task=task)
        assert False, "expected BizError"
    except BizError as exc:
        assert exc.code == 4102
        assert exc.message == "上传文件为空"


def test_initial_billing_payload_uses_quota_for_aigc(db_session, monkeypatch) -> None:
    monkeypatch.setattr(task_submission_prepare, "resolve_task_points_per_char", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(
        task_submission_prepare,
        "get_aigc_daily_quota",
        lambda *_args, **_kwargs: {"free_remaining_today": 1, "free_limit": 6},
    )

    payload = initial_billing_payload(db_session, user_id=1, task_type=TaskType.AIGC_DETECT)

    assert payload["points_per_char"] == 3.0
    assert payload["free_applied"] is True
    assert payload["quota"]["free_remaining_today"] == 1
