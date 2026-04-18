from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import DEFAULT_BILLING_PACKAGES
from app.models import CreditTransaction, Order, SystemConfig, User
from app.services.payment_service import sign_payload


def test_payment_callback_signature_and_idempotency(
    client: TestClient,
    db_session: Session,
    settings_override,
    monkeypatch,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800000001", nickname="测试用户", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(
        Order(
            order_no="ODCALLBACK0001",
            user_id=user.id,
            amount_cny=Decimal("9.90"),
            credits=10000,
            source="web",
            status="created",
            provider="wechat",
            is_first_pay=False,
        )
    )
    db_session.commit()

    payload = {
        "order_no": "ODCALLBACK0001",
        "user_id": user.id,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-001",
    }
    sign = sign_payload(payload)

    resp = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "paid"
    assert data["idempotent"] is False

    db_session.refresh(user)
    assert user.credits == 10000
    assert db_session.query(Order).filter(Order.order_no == payload["order_no"]).count() == 1
    assert (
        db_session.query(CreditTransaction).filter(CreditTransaction.related_id == payload["order_no"]).count() == 1
    )

    payload_again = {**payload, "nonce": "nonce-001-repeat"}
    sign_again = sign_payload(payload_again)
    resp2 = client.post("/api/v1/billing/callback", json={**payload_again, "sign": sign_again})
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["idempotent"] is True
    db_session.refresh(user)
    assert user.credits == 10000
    assert (
        db_session.query(CreditTransaction).filter(CreditTransaction.related_id == payload["order_no"]).count() == 1
    )


def test_payment_callback_rejects_invalid_signature(
    client: TestClient,
    db_session: Session,
    settings_override,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800000002", nickname="测试用户2", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "order_no": "ODCALLBACK0002",
        "user_id": user.id,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-002",
        "sign": "deadbeefdeadbeefdeadbeefdeadbeef",
    }
    resp = client.post("/api/v1/billing/callback", json=payload)
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 4204


def test_payment_callback_uses_payment_config_secret(
    client: TestClient,
    db_session: Session,
    settings_override,
    monkeypatch,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechat",
                "app_id": "",
                "merchant_id": "",
                "api_key": "",
                "callback_secret": "db_callback_secret_001",
            },
        )
    )
    user = User(phone="13800000003", nickname="测试用户3", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    db_session.add(
        Order(
            order_no="ODCALLBACK0003",
            user_id=user.id,
            amount_cny=Decimal("9.90"),
            credits=10000,
            source="web",
            status="created",
            provider="wechat",
            is_first_pay=False,
        )
    )
    db_session.commit()

    payload = {
        "order_no": "ODCALLBACK0003",
        "user_id": user.id,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-003",
    }
    sign = sign_payload(payload, db=db_session)
    resp = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert resp.status_code == 200


def test_payment_callback_signature_is_stable_between_float_and_decimal_amounts(
    settings_override,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    payload_float = {
        "order_no": "ODCALLBACK_DECIMAL_001",
        "user_id": 1,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-decimal-001",
    }
    payload_decimal = {**payload_float, "amount_cny": Decimal("9.90")}

    assert sign_payload(payload_float) == sign_payload(payload_decimal)


def test_payment_callback_requires_existing_order(
    client: TestClient,
    db_session: Session,
    settings_override,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800000004", nickname="测试用户4", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "order_no": "ODCALLBACK_MISSING_001",
        "user_id": user.id,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-missing-001",
    }
    sign = sign_payload(payload)
    resp = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 4044


def test_payment_callback_rejects_replayed_nonce(
    client: TestClient,
    db_session: Session,
    settings_override,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800000005", nickname="测试用户5", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    order = Order(
        order_no="ODCALLBACK_REPLAY_001",
        user_id=user.id,
        amount_cny=Decimal("9.90"),
        credits=10000,
        source="web",
        status="created",
        provider="wechat",
        is_first_pay=False,
    )
    db_session.add(order)
    db_session.commit()

    payload = {
        "order_no": order.order_no,
        "user_id": user.id,
        "package_name": package_name,
        "amount_cny": 9.9,
        "paid_at": int(datetime.now(timezone.utc).timestamp()),
        "status": "paid",
        "provider": "wechat",
        "nonce": "nonce-replay-001",
    }
    sign = sign_payload(payload)

    first = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert first.status_code == 200

    second = client.post("/api/v1/billing/callback", json={**payload, "sign": sign})
    assert second.status_code == 400
    body = second.json()
    assert body["code"] == 4205
