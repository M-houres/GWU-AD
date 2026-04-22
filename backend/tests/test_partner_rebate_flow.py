from types import SimpleNamespace

from app.deps import current_admin, current_user
from app.main import app
from app.models import (
    AdminUser,
    Order,
    PartnerChannel,
    PartnerLedgerEntryType,
    PartnerLedgerStatus,
    PartnerOrderAttribution,
    PartnerRebateLedger,
    Task,
    User,
)
from app.security import hash_password
from app.services.worker_task_support import refund_task


def _submit_dedup_text_task(client) -> int:
    resp = client.post(
        "/api/v1/tasks/submit",
        data={
            "task_type": "dedup",
            "platform": "cnki",
            "pasted_text": "这是用于渠道返佣消费测试的一段文本，用于触发真实任务扣费并产生返佣。",
            "source_filename": "sample.txt",
        },
    )
    assert resp.status_code == 200
    return int(resp.json()["data"]["id"])


def test_partner_linked_order_creates_attribution_and_consume_rebate(client, db_session) -> None:
    user = User(phone="13800003101", nickname="partner-buyer", credits=0)
    channel = PartnerChannel(
        channel_code="CHREBATE01",
        name="机构A",
        contact_name="商务",
        contact_phone="13800138000",
        status="active",
        order_token="order-token-001",
        portal_token="portal-token-001",
        default_rebate_rate_bp=1800,
    )
    db_session.add_all([user, channel])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(channel)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order?ch=CHREBATE01&ck=order-token-001",
            json={"package_name": "入门版", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]

        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        assert pay_resp.json()["data"]["status"] == "paid"
        task_id = _submit_dedup_text_task(client)
    finally:
        app.dependency_overrides.pop(current_user, None)

    order = db_session.query(Order).filter(Order.order_no == order_no).first()
    assert order is not None
    attribution = db_session.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    assert attribution is not None
    assert attribution.channel_id == channel.id
    assert attribution.attribution_source in {"link", "binding"}

    ledger = (
        db_session.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == f"TASK:{task_id}",
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.ACCRUAL,
        )
        .first()
    )
    assert ledger is not None
    assert ledger.rebate_amount_fen > 0


def test_task_refund_creates_partner_rebate_reversal(client, db_session) -> None:
    user = User(phone="13800003102", nickname="partner-refund-user", credits=10000)
    channel = PartnerChannel(
        channel_code="CHREBATE02",
        name="机构B",
        contact_name="商务",
        contact_phone="13800138001",
        status="active",
        order_token="order-token-002",
        portal_token="portal-token-002",
        default_rebate_rate_bp=1200,
    )
    db_session.add_all([user, channel])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(channel)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order?ch=CHREBATE02&ck=order-token-002",
            json={"package_name": "入门版", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]
        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        task_id = _submit_dedup_text_task(client)
    finally:
        app.dependency_overrides.pop(current_user, None)

    task = db_session.query(Task).filter(Task.id == task_id).first()
    assert task is not None
    refund_task(db_session, task)
    db_session.commit()

    reversal = (
        db_session.query(PartnerRebateLedger)
        .filter(
            PartnerRebateLedger.order_no == f"TASK:{task_id}",
            PartnerRebateLedger.entry_type == PartnerLedgerEntryType.REVERSAL,
        )
        .first()
    )
    assert reversal is not None
    assert reversal.rebate_amount_fen < 0


def test_partner_portal_and_statement_settlement(client, db_session) -> None:
    user = User(phone="13800003103", nickname="partner-portal-user", credits=0)
    channel = PartnerChannel(
        channel_code="CHREBATE03",
        name="机构C",
        contact_name="商务",
        contact_phone="13800138002",
        status="active",
        order_token="order-token-003",
        portal_token="portal-token-003",
        default_rebate_rate_bp=1000,
    )
    db_session.add_all([user, channel])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(channel)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order?ch=CHREBATE03&ck=order-token-003",
            json={"package_name": "入门版", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]
        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        _submit_dedup_text_task(client)
    finally:
        app.dependency_overrides.pop(current_user, None)

    db_session.add(
        AdminUser(
            id=2,
            username="admin2",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=2, username="admin2", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        month = client.get("/api/v1/partners/portal/overview", params={"ch": "CHREBATE03", "pk": "portal-token-003"}).json()[
            "data"
        ]["statement_month"]
        gen_resp = client.post(
            "/api/v1/partners/admin/statements/generate",
            json={"channel_id": channel.id, "statement_month": month},
        )
        assert gen_resp.status_code == 200
        statement_id = gen_resp.json()["data"]["id"]

        settle_resp = client.post(f"/api/v1/partners/admin/statements/{statement_id}/settle")
        assert settle_resp.status_code == 200
        assert settle_resp.json()["data"]["status"] == "settled"

        db_session.add(
            PartnerRebateLedger(
                channel_id=channel.id,
                order_id=None,
                order_no="MANUAL:WITHDRAW",
                user_id=user.id,
                entry_type=PartnerLedgerEntryType.ACCRUAL,
                status=PartnerLedgerStatus.SETTLED,
                base_amount_fen=100000,
                rebate_amount_fen=15000,
                statement_month=month,
                note="manual settled rebate for withdraw flow",
            )
        )
        db_session.commit()

        withdraw_apply = client.post(
            "/api/v1/partners/portal/withdraw-apply",
            params={"ch": "CHREBATE03", "pk": "portal-token-003"},
            json={"apply_amount_cny": 100, "note": "4月结算提现"},
        )
        assert withdraw_apply.status_code == 200
        withdraw_data = withdraw_apply.json()["data"]
        assert withdraw_data["status"] == "pending"
        withdraw_id = int(withdraw_data["id"])

        review_resp = client.post(
            f"/api/v1/partners/admin/withdrawals/{withdraw_id}/review",
            json={"approve": True},
        )
        assert review_resp.status_code == 200
        assert review_resp.json()["data"]["status"] == "approved"

        mark_paid_resp = client.post(f"/api/v1/partners/admin/withdrawals/{withdraw_id}/mark-paid")
        assert mark_paid_resp.status_code == 200
        assert mark_paid_resp.json()["data"]["status"] == "paid"
    finally:
        app.dependency_overrides.pop(current_admin, None)

    portal_orders = client.get(
        "/api/v1/partners/portal/orders",
        params={"ch": "CHREBATE03", "pk": "portal-token-003"},
    )
    assert portal_orders.status_code == 200
    order_nos = [item["order_no"] for item in portal_orders.json()["data"]["items"]]
    assert order_no in order_nos

    portal_statements = client.get(
        "/api/v1/partners/portal/statements",
        params={"ch": "CHREBATE03", "pk": "portal-token-003"},
    )
    assert portal_statements.status_code == 200
    assert len(portal_statements.json()["data"]["items"]) >= 1

    portal_withdrawals = client.get(
        "/api/v1/partners/portal/withdrawals",
        params={"ch": "CHREBATE03", "pk": "portal-token-003"},
    )
    assert portal_withdrawals.status_code == 200
    withdrawal_items = portal_withdrawals.json()["data"]["items"]
    assert len(withdrawal_items) >= 1
    assert any(item["status"] == "paid" for item in withdrawal_items)
