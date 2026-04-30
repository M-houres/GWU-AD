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
    PartnerPolicy,
    PartnerRebateLedger,
    Task,
    SystemConfig,
    User,
)
from app.security import hash_password
from app.services.partner_rebate_service import build_channel_scene_value, create_partner_channel, update_partner_channel, upsert_partner_policy
from app.services.worker_task_support import refund_task
from app.exceptions import BizError


def _issue_partner_portal_token(client, db_session, channel: PartnerChannel, *, admin_id: int, admin_username: str) -> tuple[str, str]:
    db_session.add(
        AdminUser(
            id=admin_id,
            username=admin_username,
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    db_session.refresh(channel)

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=admin_id,
        username=admin_username,
        role="super_admin",
        is_active=True,
        permissions_json=["*"],
    )
    try:
        reset_resp = client.post(f"/api/v1/partners/admin/channels/{channel.id}/portal-password/reset")
        assert reset_resp.status_code == 200
        portal_password = str(reset_resp.json()["data"]["portal_password"])
    finally:
        app.dependency_overrides.pop(current_admin, None)

    login_resp = client.post(
        "/api/v1/partners/portal/auth/login",
        json={"account": channel.channel_code, "password": portal_password},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()["data"]
    return str(login_data["token"]), str(login_data["refresh_token"])


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
            json={"package_name": "体验包", "provider": "mock"},
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


def test_partner_scene_order_creates_attribution(client, db_session) -> None:
    user = User(phone="13800003111", nickname="partner-scene-buyer", credits=0)
    channel = PartnerChannel(
        channel_code="CHSCORD1",
        name="场景下单渠道",
        contact_name="商务",
        contact_phone="13800138111",
        status="active",
        order_token="order-scene-token-001",
        portal_token="portal-scene-token-001",
        default_rebate_rate_bp=1500,
    )
    db_session.add_all([user, channel])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(channel)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order",
            json={
                "package_name": "体验包",
                "provider": "mock",
                "channel_scene": build_channel_scene_value(channel),
            },
            headers={"X-Client-Source": "miniprogram"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]
    finally:
        app.dependency_overrides.pop(current_user, None)

    order = db_session.query(Order).filter(Order.order_no == order_no).first()
    assert order is not None
    attribution = db_session.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.order_id == order.id).first()
    assert attribution is not None
    assert attribution.channel_id == channel.id
    assert attribution.attribution_source in {"link", "binding"}


def test_miniprogram_phone_login_binds_partner_tracking(client, db_session) -> None:
    from app.config import get_settings

    settings = get_settings()
    old_env = settings.app_env
    settings.app_env = "dev"
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx-mini-dev-009",
                "wechat_miniprogram_app_secret": "mini-dev-secret-009",
            },
        )
    )
    channel = PartnerChannel(
        channel_code="CHLOGIN01",
        name="登录渠道",
        contact_name="商务",
        contact_phone="13800138009",
        status="active",
        order_token="login-token-001",
        portal_token="portal-token-009",
        default_rebate_rate_bp=1200,
    )
    db_session.add(channel)
    db_session.commit()

    try:
        resp = client.post(
            "/api/v1/auth/wx/mini-phone-login",
            json={
                "login_code": "mock_login_code_009",
                "phone_code": "mock_phone_13800009999",
                "channel_code": "CHLOGIN01",
                "channel_token": "login-token-001",
            },
            headers={"X-Client-Source": "miniprogram"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        tracking = body["data"]["user"]["partner_tracking"]
        assert tracking is not None
        assert tracking["channel_code"] == "CHLOGIN01"
        assert tracking["bind_source"] == "mini_phone_login"
    finally:
        settings.app_env = old_env


def test_miniprogram_phone_login_binds_partner_tracking_by_scene(client, db_session) -> None:
    from app.config import get_settings

    settings = get_settings()
    old_env = settings.app_env
    settings.app_env = "dev"
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx-mini-dev-010",
                "wechat_miniprogram_app_secret": "mini-dev-secret-010",
            },
        )
    )
    channel = PartnerChannel(
        channel_code="CHSCENE01",
        name="场景渠道",
        contact_name="商务",
        contact_phone="13800138010",
        status="active",
        order_token="scene-token-001",
        portal_token="scene-portal-001",
        default_rebate_rate_bp=1200,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)

    try:
        resp = client.post(
            "/api/v1/auth/wx/mini-phone-login",
            json={
                "login_code": "mock_login_code_010",
                "phone_code": "mock_phone_13800001010",
                "channel_scene": build_channel_scene_value(channel),
            },
            headers={"X-Client-Source": "miniprogram"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        tracking = body["data"]["user"]["partner_tracking"]
        assert tracking is not None
        assert tracking["channel_code"] == "CHSCENE01"
        assert tracking["bind_source"] == "mini_phone_login"
    finally:
        settings.app_env = old_env


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
            json={"package_name": "体验包", "provider": "mock"},
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
            json={"package_name": "体验包", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]
        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        _submit_dedup_text_task(client)
    finally:
        app.dependency_overrides.pop(current_user, None)

    portal_token, _ = _issue_partner_portal_token(client, db_session, channel, admin_id=2, admin_username="admin2")
    portal_headers = {"Authorization": f"Bearer {portal_token}"}
    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=2, username="admin2", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        month = client.get("/api/v1/partners/portal/overview", headers=portal_headers).json()["data"]["statement_month"]
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
            headers=portal_headers,
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
        headers=portal_headers,
    )
    assert portal_orders.status_code == 200
    order_nos = [item["order_no"] for item in portal_orders.json()["data"]["items"]]
    assert order_no in order_nos

    portal_statements = client.get(
        "/api/v1/partners/portal/statements",
        headers=portal_headers,
    )
    assert portal_statements.status_code == 200
    assert len(portal_statements.json()["data"]["items"]) >= 1

    portal_withdrawals = client.get(
        "/api/v1/partners/portal/withdrawals",
        headers=portal_headers,
    )
    assert portal_withdrawals.status_code == 200
    withdrawal_items = portal_withdrawals.json()["data"]["items"]
    assert len(withdrawal_items) >= 1
    assert any(item["status"] == "paid" for item in withdrawal_items)

    portal_overview = client.get(
        "/api/v1/partners/portal/overview",
        headers=portal_headers,
    )
    assert portal_overview.status_code == 200
    overview_data = portal_overview.json()["data"]
    assert "miniapp_order_path" in overview_data
    assert "miniapp_portal_path" not in overview_data


def test_partner_portal_login_and_password_only_access(client, db_session) -> None:
    channel = PartnerChannel(
        channel_code="CHLOGIN01",
        name="登录渠道",
        contact_name="商务",
        contact_phone="13800138022",
        status="active",
        order_token="order-token-login",
        portal_token="portal-token-login",
        default_rebate_rate_bp=1600,
    )
    db_session.add(channel)
    db_session.add(
        AdminUser(
            id=12,
            username="admin-login",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    db_session.refresh(channel)

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=12, username="admin-login", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        reset_resp = client.post(f"/api/v1/partners/admin/channels/{channel.id}/portal-password/reset")
        assert reset_resp.status_code == 200
        reset_data = reset_resp.json()["data"]
        password = str(reset_data["portal_password"])
    finally:
        app.dependency_overrides.pop(current_admin, None)

    login_resp = client.post(
        "/api/v1/partners/portal/auth/login",
        json={"account": channel.channel_code, "password": password},
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()["data"]
    token = str(login_data["token"])
    refresh_token = str(login_data["refresh_token"])
    assert token
    assert refresh_token

    overview_resp = client.get(
        "/api/v1/partners/portal/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert overview_resp.status_code == 200
    assert overview_resp.json()["data"]["channel_code"] == channel.channel_code

    refresh_resp = client.post(
        "/api/v1/partners/portal/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    refreshed_token = str(refresh_resp.json()["data"]["token"])
    assert refreshed_token

    change_password_resp = client.post(
        "/api/v1/partners/portal/auth/change-password",
        headers={"Authorization": f"Bearer {refreshed_token}"},
        json={"old_password": password, "new_password": "NewPassw0rd!456"},
    )
    assert change_password_resp.status_code == 200
    assert change_password_resp.json()["message"] == "密码已更新"

    old_login_resp = client.post(
        "/api/v1/partners/portal/auth/login",
        json={"account": channel.channel_code, "password": password},
    )
    assert old_login_resp.status_code == 403

    relogin_resp = client.post(
        "/api/v1/partners/portal/auth/login",
        json={"account": channel.channel_code, "password": "NewPassw0rd!456"},
    )
    assert relogin_resp.status_code == 200
    relogin_token = str(relogin_resp.json()["data"]["token"])
    assert relogin_token

    exchange_resp = client.post(
        "/api/v1/partners/portal/auth/exchange",
        json={"channel_code": channel.channel_code, "portal_token": channel.portal_token},
    )
    assert exchange_resp.status_code == 410

    client.cookies.clear()
    legacy_overview_resp = client.get(
        "/api/v1/partners/portal/overview",
        params={"ch": channel.channel_code, "pk": channel.portal_token},
    )
    assert legacy_overview_resp.status_code == 401

    customers_resp = client.get(
        "/api/v1/partners/portal/customers",
        headers={"Authorization": f"Bearer {relogin_token}"},
    )
    assert customers_resp.status_code == 200


def test_partner_multilevel_rebate_and_binding_lock(client, db_session) -> None:
    user = User(phone="13800003104", nickname="partner-multilevel-user", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    root = create_partner_channel(
        db_session,
        name="一级代理",
        contact_name="张三",
        contact_phone="13800138010",
        channel_code="CHROOT01",
        rebate_rate_bp=3000,
    )
    child = create_partner_channel(
        db_session,
        name="二级代理",
        contact_name="李四",
        contact_phone="13800138011",
        channel_code="CHCHILD1",
        rebate_rate_bp=1800,
        parent_channel_id=root.id,
    )
    try:
        create_partner_channel(
            db_session,
            name="三级代理",
            contact_name="王五",
            contact_phone="13800138012",
            channel_code="CHGRAND1",
            rebate_rate_bp=1000,
            parent_channel_id=child.id,
        )
        raise AssertionError("expected third-level partner creation to be blocked")
    except BizError as exc:
        assert exc.code == 4477
        assert "最多支持 2 级" in exc.message


def test_update_partner_default_rate_syncs_default_policy(db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级代理A",
        contact_name="张三",
        contact_phone="13800138100",
        channel_code="CHROOTA1",
        rebate_rate_bp=3000,
    )
    child = create_partner_channel(
        db_session,
        name="二级代理A",
        contact_name="李四",
        contact_phone="13800138101",
        channel_code="CHILDA11",
        rebate_rate_bp=1500,
        parent_channel_id=root.id,
    )
    db_session.commit()

    update_partner_channel(db_session, channel=child, rebate_rate_bp=2200)
    db_session.commit()
    db_session.refresh(child)

    default_policy = db_session.query(PartnerPolicy).filter(
        PartnerPolicy.channel_id == child.id,
        PartnerPolicy.package_name.is_(None),
    ).first()
    assert child.default_rebate_rate_bp == 2200
    assert default_policy is not None
    assert int(default_policy.rebate_rate_bp or 0) == 2200


def test_child_package_policy_cannot_exceed_parent_package_rate(db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级代理B",
        contact_name="张三",
        contact_phone="13800138110",
        channel_code="CHROOTB1",
        rebate_rate_bp=3000,
    )
    child = create_partner_channel(
        db_session,
        name="二级代理B",
        contact_name="李四",
        contact_phone="13800138111",
        channel_code="CHILDB11",
        rebate_rate_bp=1800,
        parent_channel_id=root.id,
    )
    db_session.commit()

    upsert_partner_policy(
        db_session,
        channel_id=root.id,
        package_name="高阶包",
        rebate_rate_bp=1800,
        is_active=True,
    )
    db_session.commit()

    try:
        upsert_partner_policy(
            db_session,
            channel_id=child.id,
            package_name="高阶包",
            rebate_rate_bp=2000,
            is_active=True,
        )
    except BizError as exc:
        assert exc.code == 4478
    else:
        raise AssertionError("expected child package policy to be rejected")


def test_parent_cannot_lower_package_policy_below_existing_child_policy(db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级代理C",
        contact_name="张三",
        contact_phone="13800138120",
        channel_code="CHROOTC1",
        rebate_rate_bp=3000,
    )
    child = create_partner_channel(
        db_session,
        name="二级代理C",
        contact_name="李四",
        contact_phone="13800138121",
        channel_code="CHILDC11",
        rebate_rate_bp=1800,
        parent_channel_id=root.id,
    )
    db_session.commit()

    upsert_partner_policy(
        db_session,
        channel_id=root.id,
        package_name="高阶包",
        rebate_rate_bp=2500,
        is_active=True,
    )
    upsert_partner_policy(
        db_session,
        channel_id=child.id,
        package_name="高阶包",
        rebate_rate_bp=2200,
        is_active=True,
    )
    db_session.commit()

    try:
        upsert_partner_policy(
            db_session,
            channel_id=root.id,
            package_name="高阶包",
            rebate_rate_bp=2100,
            is_active=True,
        )
    except BizError as exc:
        assert exc.code == 4480
    else:
        raise AssertionError("expected parent package policy downgrade to be rejected")


def test_partner_team_summary_and_customer_scope(client, db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级团队",
        contact_name="张一",
        contact_phone="13800138200",
        channel_code="CHTEAMR1",
        rebate_rate_bp=3000,
    )
    child = create_partner_channel(
        db_session,
        name="二级团队",
        contact_name="张二",
        contact_phone="13800138201",
        channel_code="CHTEAMC2",
        rebate_rate_bp=1800,
        parent_channel_id=root.id,
    )
    db_session.commit()
    db_session.refresh(root)
    db_session.refresh(child)

    user = User(phone="13800003888", nickname="team-user", credits=0)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            f"/api/v1/billing/create-order?ch={child.channel_code}&ck={child.order_token}",
            json={"package_name": "体验包", "provider": "mock"},
        )
        assert create_resp.status_code == 200
        order_no = create_resp.json()["data"]["order_no"]
        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
    finally:
        app.dependency_overrides.pop(current_user, None)

    portal_token, _ = _issue_partner_portal_token(client, db_session, root, admin_id=31, admin_username="admin-team-summary")
    portal_headers = {"Authorization": f"Bearer {portal_token}"}

    team_summary = client.get(
        "/api/v1/partners/portal/team-summary",
        headers=portal_headers,
        params={"scope": "subtree"},
    )
    assert team_summary.status_code == 200
    assert team_summary.json()["data"]["order_count"] >= 1

    customers_resp = client.get(
        "/api/v1/partners/portal/customers",
        headers=portal_headers,
        params={"scope": "subtree"},
    )
    assert customers_resp.status_code == 200
    customer_items = customers_resp.json()["data"]["items"]
    assert len(customer_items) >= 1
    assert any(item["channel_code"] == child.channel_code for item in customer_items)


def test_admin_create_root_channel_returns_initial_portal_password(client, db_session) -> None:
    db_session.add(
        AdminUser(
            id=21,
            username="admin-root-create",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=21, username="admin-root-create", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        resp = client.post(
            "/api/v1/partners/admin/channels",
            json={
                "name": "一级渠道新建测试",
                "contact_name": "赵六",
                "contact_phone": "13800138999",
                "rebate_rate_bp": 1800,
            },
        )
    finally:
        app.dependency_overrides.pop(current_admin, None)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["level"] == 1
    assert data["portal_account"]
    assert data["portal_password"]


def test_admin_cannot_create_child_channel_directly(client, db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="平台一级渠道",
        contact_name="张三",
        contact_phone="13800138888",
        channel_code="CHADMINR1",
        rebate_rate_bp=2200,
    )
    db_session.add(
        AdminUser(
            id=22,
            username="admin-child-block",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    db_session.refresh(root)

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=22, username="admin-child-block", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        resp = client.post(
            f"/api/v1/partners/admin/channels/{root.id}/children",
            json={
                "name": "不允许的平台下级",
                "contact_name": "李四",
                "contact_phone": "13800138777",
                "rebate_rate_bp": 1200,
            },
        )
    finally:
        app.dependency_overrides.pop(current_admin, None)

    assert resp.status_code == 400
    assert "平台后台不直接创建下级" in resp.json()["message"]


def test_portal_create_subchannel_returns_initial_portal_password(client, db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级渠道门户",
        contact_name="张三",
        contact_phone="13800138666",
        channel_code="CHPORTAL1",
        rebate_rate_bp=2500,
    )
    db_session.commit()
    db_session.refresh(root)

    portal_token, _ = _issue_partner_portal_token(client, db_session, root, admin_id=32, admin_username="admin-portal-child")
    portal_headers = {"Authorization": f"Bearer {portal_token}"}

    resp = client.post(
        "/api/v1/partners/portal/subchannels",
        headers=portal_headers,
        json={
            "name": "二级渠道门户",
            "contact_name": "李四",
            "contact_phone": "13800138555",
            "rebate_rate_bp": 1500,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["level"] == 2
    assert data["portal_account"]
    assert data["portal_password"]

    reset_resp = client.post(
        f"/api/v1/partners/portal/subchannels/{data['id']}/portal-password/reset",
        headers=portal_headers,
    )
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()["data"]
    assert reset_data["portal_account"]
    assert reset_data["portal_password"]


def test_admin_can_delete_empty_root_channel_with_name_confirmation(client, db_session) -> None:
    channel = create_partner_channel(
        db_session,
        name="待删除一级渠道",
        contact_name="张三",
        contact_phone="13800138444",
        channel_code="CHDELROOT",
        rebate_rate_bp=1800,
    )
    db_session.add(
        AdminUser(
            id=23,
            username="admin-delete-channel",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    db_session.refresh(channel)

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=23, username="admin-delete-channel", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        resp = client.request(
            "DELETE",
            f"/api/v1/partners/admin/channels/{channel.id}",
            json={"confirm_name": channel.name},
        )
    finally:
        app.dependency_overrides.pop(current_admin, None)

    assert resp.status_code == 200
    assert resp.json()["message"] == "渠道已删除"
    deleted = db_session.query(PartnerChannel).filter(PartnerChannel.id == channel.id).first()
    assert deleted is None


def test_admin_partner_analytics_status_filter_uses_visible_child_scope(client, db_session) -> None:
    root = create_partner_channel(
        db_session,
        name="一级可见渠道",
        contact_name="张三",
        contact_phone="13800138445",
        channel_code="CHANALYT1",
        rebate_rate_bp=1800,
    )
    hidden_child = create_partner_channel(
        db_session,
        name="停用二级渠道",
        contact_name="李四",
        contact_phone="13800138446",
        channel_code="CHANALYT2",
        rebate_rate_bp=1200,
        parent_channel_id=root.id,
    )
    hidden_child.status = "disabled"
    healthy_root = create_partner_channel(
        db_session,
        name="一级正常渠道",
        contact_name="王五",
        contact_phone="13800138447",
        channel_code="CHANALYT3",
        rebate_rate_bp=1800,
    )
    create_partner_channel(
        db_session,
        name="活跃二级但名称不匹配",
        contact_name="赵六",
        contact_phone="13800138448",
        channel_code="CHANALYT4",
        rebate_rate_bp=1200,
        parent_channel_id=healthy_root.id,
    )
    db_session.add(
        AdminUser(
            id=24,
            username="admin-analytics-scope",
            password_hash=hash_password("Passw0rd!123"),
            role="super_admin",
            is_active=True,
            permissions_json=[],
        )
    )
    db_session.commit()
    db_session.refresh(root)

    app.dependency_overrides[current_admin] = lambda: SimpleNamespace(
        id=24, username="admin-analytics-scope", role="super_admin", is_active=True, permissions_json=["*"]
    )
    try:
        resp = client.get(
            "/api/v1/partners/admin/analytics",
            params={"status": "active", "keyword": root.channel_code},
        )
        healthy_resp = client.get(
            "/api/v1/partners/admin/analytics",
            params={"status": "active", "keyword": healthy_root.channel_code},
        )
    finally:
        app.dependency_overrides.pop(current_admin, None)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["summary"]["root_channel_count"] == 1
    assert any(item["type"] == "no-child" and item["channel_id"] == root.id for item in data["anomalies"])
    assert healthy_resp.status_code == 200
    healthy_data = healthy_resp.json()["data"]
    assert healthy_data["summary"]["root_channel_count"] == 1
    assert not any(item["type"] == "no-child" and item["channel_id"] == healthy_root.id for item in healthy_data["anomalies"])
