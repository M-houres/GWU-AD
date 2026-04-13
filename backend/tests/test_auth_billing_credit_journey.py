from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import CreditTransaction, User


def _send_code_and_get_debug_code(client: TestClient, phone: str, *, ip: str = "10.10.10.20") -> str:
    resp = client.post(
        "/api/v1/auth/send-code",
        json={"phone": phone},
        headers={"x-forwarded-for": ip, "user-agent": "pytest-journey"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["debug_code"])


def test_new_user_payment_journey_keeps_credit_ledger_consistent(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.worker_tasks.grant_order_referral_rewards_async.delay", lambda *_args, **_kwargs: None)

    phone = "13800006300"
    code = _send_code_and_get_debug_code(client, phone)
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": code},
        headers={"x-forwarded-for": "10.10.10.20", "user-agent": "pytest-journey"},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()["data"]
    assert login_data["is_new_user"] is True
    user_id = int(login_data["user"]["id"])
    user = db_session.get(User, user_id)
    assert user is not None
    initial_credits = int(user.credits)

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order",
            json={"package_name": "入门包", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]

        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        assert pay_resp.json()["data"]["status"] == "paid"
        assert pay_resp.json()["data"]["idempotent"] is False

        repeat_pay = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert repeat_pay.status_code == 200
        assert repeat_pay.json()["data"]["idempotent"] is True

        me_resp = client.get("/api/v1/users/me")
        assert me_resp.status_code == 200
        tx_resp = client.get("/api/v1/users/me/credit-transactions")
        assert tx_resp.status_code == 200
        tx_items = tx_resp.json()["data"]["items"]
        related_ids = {item["related_id"] for item in tx_items}
        tx_types = {item["tx_type"] for item in tx_items}
        assert order_no in related_ids
        assert "package_pay" in tx_types
    finally:
        app.dependency_overrides.pop(current_user, None)

    db_session.refresh(user)
    user_transactions = db_session.query(CreditTransaction).filter(CreditTransaction.user_id == user.id).all()
    assert user.credits == sum(int(row.delta) for row in user_transactions)
