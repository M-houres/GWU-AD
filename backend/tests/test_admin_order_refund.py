from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditTransaction, CreditType, Order, User


def test_admin_refund_paid_order(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    user = User(phone="13800007777", nickname="u3", credits=10000)
    db_session.add(user)
    db_session.flush()

    order = Order(
        order_no="OD_REFUND_001",
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
    data = resp.json()["data"]
    assert data["status"] == "refunded"

    db_session.refresh(order)
    db_session.refresh(user)
    assert order.status == "refunded"
    assert user.credits == 0

    idempotent = client.post(f"/api/v1/admin/orders/{order.order_no}/refund")
    assert idempotent.status_code == 200
    assert idempotent.json()["data"]["idempotent"] is True


def test_admin_order_detail_returns_package_snapshot(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    user = User(phone="13800007778", nickname="order-detail-user", credits=13000)
    db_session.add(user)
    db_session.flush()

    order = Order(
        order_no="OD_DETAIL_001",
        user_id=user.id,
        amount_cny=19.9,
        credits=13000,
        package_snapshot={
            "name": "体验包",
            "price": 19.9,
            "credits": 13000,
            "processable_chars": 13000,
            "price_per_kchar": 1.53,
            "badge": "新手体验",
            "description": "适合短篇体验",
            "audience": "C端新人体验",
            "discount_note": "贴近原价 1.5，几乎无优惠",
            "sort_order": 1,
        },
        status="paid",
        provider="mock",
        is_first_pay=True,
    )
    db_session.add(order)
    db_session.commit()

    resp = client.get(f"/api/v1/admin/orders/{order.order_no}/detail")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["package_snapshot"]["name"] == "体验包"
    assert data["package_snapshot"]["processable_chars"] == 13000
    assert data["package_snapshot"]["audience"] == "C端新人体验"
