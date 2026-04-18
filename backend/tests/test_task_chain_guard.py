from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.api.tasks import TASK_CHAIN_GUARD_TIMEOUT_MESSAGE
from app.deps import current_user
from app.main import app
from app.models import CreditTransaction, CreditType, Task, TaskStatus, TaskType, User


def test_my_tasks_guard_marks_stale_queued_failed_and_refunds(client, db_session: Session) -> None:
    user = User(phone="13800009991", nickname="guard-user-1", credits=800)
    db_session.add(user)
    db_session.flush()

    stale_anchor = datetime.utcnow() - timedelta(hours=3)
    task = Task(
        user_id=user.id,
        task_type=TaskType.DEDUP,
        platform="cnki",
        source="web",
        status=TaskStatus.QUEUED,
        source_filename="guard.docx",
        source_path="/tmp/guard.docx",
        char_count=1280,
        cost_credits=200,
        refund_done=False,
        created_at=stale_anchor,
        updated_at=stale_anchor,
    )
    db_session.add(task)
    db_session.flush()
    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.TASK_CONSUME,
            delta=-200,
            balance_before=1000,
            balance_after=800,
            reason="dedup任务提交扣费",
            related_id=f"task:{task.id}",
            source="web",
        )
    )
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get("/api/v1/tasks/my")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        row = next(item for item in items if int(item["id"]) == task.id)
        assert row["status"] == "failed"
        assert row["refund_done"] is True
        assert TASK_CHAIN_GUARD_TIMEOUT_MESSAGE in str(row.get("error_message", ""))
    finally:
        app.dependency_overrides.pop(current_user, None)

    db_session.refresh(task)
    db_session.refresh(user)
    assert task.status == TaskStatus.FAILED
    assert task.refund_done is True
    assert user.credits == 1000

    refunds = (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user.id,
            CreditTransaction.tx_type == CreditType.TASK_REFUND,
            CreditTransaction.related_id == f"task_refund:{task.id}",
        )
        .all()
    )
    assert len(refunds) == 1
    assert refunds[0].delta == 200


def test_task_detail_guard_keeps_fresh_processing_task_unchanged(client, db_session: Session) -> None:
    user = User(phone="13800009992", nickname="guard-user-2", credits=5000)
    db_session.add(user)
    db_session.flush()

    fresh_anchor = datetime.utcnow() - timedelta(seconds=30)
    task = Task(
        user_id=user.id,
        task_type=TaskType.REWRITE,
        platform="cnki",
        source="web",
        status=TaskStatus.RUNNING,
        source_filename="fresh.docx",
        source_path="/tmp/fresh.docx",
        char_count=3200,
        cost_credits=6400,
        refund_done=False,
        created_at=fresh_anchor,
        updated_at=fresh_anchor,
    )
    db_session.add(task)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.get(f"/api/v1/tasks/{task.id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "running"
        assert resp.json()["data"]["refund_done"] is False
    finally:
        app.dependency_overrides.pop(current_user, None)

    db_session.refresh(task)
    assert task.status == TaskStatus.RUNNING
