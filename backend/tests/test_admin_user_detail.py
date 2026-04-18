from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditTransaction, CreditType, Order, Task, TaskStatus, TaskType, User


def test_admin_user_detail_returns_summary(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    user = User(phone="13800009999", nickname="u1", credits=120)
    db_session.add(user)
    db_session.flush()

    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.INIT,
            delta=120,
            balance_before=0,
            balance_after=120,
            reason="init",
            related_id=f"init:{user.id}",
        )
    )
    db_session.add(
        Task(
            user_id=user.id,
            task_type=TaskType.DEDUP,
            platform="cnki",
            status=TaskStatus.COMPLETED,
            source_filename="a.docx",
            source_path="/tmp/a.docx",
            char_count=100,
            cost_credits=200,
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()

    resp = client.get(f"/api/v1/admin/users/{user.id}/detail")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["id"] == user.id
    assert isinstance(data["credit_transactions"], list)
    assert isinstance(data["tasks"], list)
    assert data["tasks"][0]["source_filename"] == "a.docx"
    assert "result_json" in data["tasks"][0]
    assert "updated_at" in data["tasks"][0]


def test_admin_user_ban_toggle(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    user = User(phone="13800008888", nickname="u2", credits=0, is_banned=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = client.post(f"/api/v1/admin/users/{user.id}/ban", json={"is_banned": True})
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.is_banned is True


def test_admin_endpoints_track_miniprogram_source_consistently(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    user = User(phone="13800007777", nickname="mini-user", credits=2000, source="miniprogram")
    db_session.add(user)
    db_session.flush()

    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.INIT,
            delta=2000,
            balance_before=0,
            balance_after=2000,
            reason="mini init",
            related_id=f"init:{user.id}",
            source="miniprogram",
        )
    )
    db_session.add(
        Task(
            user_id=user.id,
            task_type=TaskType.AIGC_DETECT,
            platform="cnki",
            status=TaskStatus.COMPLETED,
            source="miniprogram",
            source_filename="mini.docx",
            source_path="/tmp/mini.docx",
            char_count=1200,
            cost_credits=1200,
            created_at=datetime.utcnow(),
        )
    )
    db_session.add(
        Order(
            order_no="GWMINI202604180001",
            user_id=user.id,
            amount_cny=19,
            credits=10000,
            source="miniprogram",
            status="paid",
            provider="wechat",
            is_first_pay=True,
        )
    )
    db_session.commit()

    users_resp = client.get("/api/v1/admin/users?source=miniapp")
    assert users_resp.status_code == 200
    users_data = users_resp.json()["data"]
    assert users_data["source_filter"] == "miniapp"
    assert users_data["source_stats"]["miniapp"] >= 1
    assert users_data["items"][0]["source"] == "miniapp"

    tasks_resp = client.get("/api/v1/admin/tasks?source=miniprogram")
    assert tasks_resp.status_code == 200
    tasks_data = tasks_resp.json()["data"]
    assert tasks_data["source_filter"] == "miniapp"
    assert tasks_data["source_stats"]["miniapp"] >= 1
    assert tasks_data["items"][0]["source"] == "miniapp"

    orders_resp = client.get("/api/v1/admin/orders?source=wechat_miniprogram")
    assert orders_resp.status_code == 200
    orders_data = orders_resp.json()["data"]
    assert orders_data["source_filter"] == "miniapp"
    assert orders_data["source_stats"]["orders"]["miniapp"] >= 1
    assert orders_data["items"][0]["source"] == "miniapp"

    detail_resp = client.get(f"/api/v1/admin/users/{user.id}/detail")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert detail_data["user"]["source"] == "miniapp"
    assert detail_data["credit_transactions"][0]["source"] == "miniapp"
    assert detail_data["tasks"][0]["source"] == "miniapp"
