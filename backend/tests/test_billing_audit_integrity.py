from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AdminAuditLog, AdminUser, CreditTransaction, CreditType, Order, User
from app.services.payment_service import sign_payload


def test_payment_callback_amount_mismatch_rejected(client: TestClient, db_session: Session, settings_override) -> None:
    user = User(phone="13800006200", nickname="pay-user", credits=0)
    db_session.add(user)
    db_session.add(
        Order(
            order_no="ODCALLBACK_AMT_001",
            user_id=1,
            amount_cny=9.9,
            credits=10000,
            status="created",
            provider="wechat",
            is_first_pay=False,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "order_no": "ODCALLBACK_AMT_001",
        "user_id": user.id,
        "package_name": "入门包",
        "amount_cny": 19.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-amt-001",
    }
    sign = sign_payload(payload)

    resp = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert resp.status_code == 400
    assert resp.json()["code"] == 4207

    order = db_session.query(Order).filter(Order.order_no == "ODCALLBACK_AMT_001").first()
    assert order is not None
    assert order.status == "created"
    assert db_session.query(CreditTransaction).filter(CreditTransaction.related_id == order.order_no).count() == 0


def test_order_status_remote_paid_is_idempotent_after_callback(
    client: TestClient,
    db_session: Session,
    settings_override,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.worker_tasks.grant_order_referral_rewards_async.delay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.api.billing.query_remote_order_status",
        lambda *_args, **_kwargs: {"status": "paid", "amount_cny": 9.9},
    )

    user = User(phone="13800006201", nickname="pay-user-2", credits=0)
    db_session.add(user)
    order = Order(
        order_no="OD_REMOTE_IDEM_001",
        user_id=1,
        amount_cny=9.9,
        credits=10000,
        status="created",
        provider="wechat",
        is_first_pay=False,
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "order_no": order.order_no,
        "user_id": user.id,
        "package_name": "入门包",
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-idem-001",
    }
    sign = sign_payload(payload)
    callback_resp = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert callback_resp.status_code == 200
    assert callback_resp.json()["data"]["idempotent"] is False

    from app.deps import current_user
    from app.main import app

    app.dependency_overrides[current_user] = lambda: user
    try:
        status_resp = client.get(f"/api/v1/billing/order-status/{order.order_no}")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] == "paid"
    finally:
        app.dependency_overrides.pop(current_user, None)

    db_session.refresh(user)
    assert user.credits == 10000
    assert db_session.query(CreditTransaction).filter(CreditTransaction.related_id == order.order_no).count() == 1


def test_admin_adjust_credits_writes_audit_log(client: TestClient, db_session: Session, admin_override) -> None:
    db_session.add(AdminUser(id=1, username="admin", password_hash="x", role="super_admin"))
    user = User(phone="13800006202", nickname="audit-user", credits=100)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    resp = client.post(f"/api/v1/admin/users/{user.id}/adjust-credits", json={"delta": 50, "reason": "补偿"})
    assert resp.status_code == 200
    db_session.refresh(user)
    assert user.credits == 150

    row = (
        db_session.query(AdminAuditLog)
        .filter(AdminAuditLog.action == "user_credit_adjust", AdminAuditLog.target_id == str(user.id))
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    assert row is not None
    assert row.target_type == "user"
    assert row.before_json == {"credits": 100, "delta": 50}
    assert row.after_json == {"credits": 150, "delta": 50, "reason": "补偿"}


def test_admin_refund_writes_audit_log_with_before_after_status(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(AdminUser(id=1, username="admin", password_hash="x", role="super_admin"))
    user = User(phone="13800006203", nickname="refund-audit-user", credits=10000)
    db_session.add(user)
    db_session.flush()

    order = Order(
        order_no="OD_REFUND_AUDIT_001",
        user_id=user.id,
        amount_cny=9.9,
        credits=10000,
        status="paid",
        provider="mock",
        is_first_pay=True,
    )
    db_session.add(order)
    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.PACKAGE_PAY,
            delta=10000,
            balance_before=0,
            balance_after=10000,
            reason="充值",
            related_id=order.order_no,
        )
    )
    db_session.commit()

    resp = client.post(f"/api/v1/admin/orders/{order.order_no}/refund")
    assert resp.status_code == 200

    audit = (
        db_session.query(AdminAuditLog)
        .filter(AdminAuditLog.action == "order_refund", AdminAuditLog.target_id == order.order_no)
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert audit.target_type == "order"
    assert audit.before_json == {"status": "paid"}
    assert audit.after_json == {"status": "refunded"}
