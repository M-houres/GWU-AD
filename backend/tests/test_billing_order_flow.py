from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.constants import DEFAULT_BILLING_PACKAGES
from app.deps import current_user, db_dep
from app.exceptions import BizError
from app.main import app
from app.models import Order, SystemConfig, User
from app.services.payment_service import create_payment_session


def test_create_order_poll_and_pay_with_remote_provider(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.worker_tasks.grant_order_referral_rewards_async.delay", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.api.billing.create_payment_session",
        lambda *_args, **_kwargs: {"provider": "wechat", "pay_url": "weixin://wxpay/mock"},
    )
    monkeypatch.setattr(
        "app.api.billing.query_remote_order_status",
        lambda *_args, **_kwargs: {"status": "paid", "amount_cny": 9.9},
    )

    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800006666", nickname="u4", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechatpay_v3",
                "test_mode": False,
                "app_id": "wx123",
                "merchant_id": "1900000109",
                "merchant_serial_no": "SERIAL001",
                "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                "api_v3_key": "12345678901234567890123456789012",
                "notify_url": "https://example.com",
            },
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post("/api/v1/billing/create-order", json={"package_name": package_name, "provider": "wechat"})
        assert create_resp.status_code == 200
        create_data = create_resp.json()["data"]
        order_no = create_data["order_no"]
        assert create_data["status"] == "created"

        status_resp = client.get(f"/api/v1/billing/order-status/{order_no}")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["status"] == "paid"

        pay_resp = client.post(f"/api/v1/billing/order-pay/{order_no}")
        assert pay_resp.status_code == 200
        pay_data = pay_resp.json()["data"]
        assert pay_data["status"] == "paid"

        row = db_session.query(Order).filter(Order.order_no == order_no).first()
        assert row is not None
        assert row.status == "paid"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_create_order_for_miniprogram_returns_payment_params(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    captured: dict = {}

    def _mock_create_payment_session(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "provider": "wechat",
            "scene": "miniprogram",
            "payment_params": {
                "timeStamp": "1710000000",
                "nonceStr": "nonce123",
                "package": "prepay_id=wx_mock_prepay",
                "signType": "RSA",
                "paySign": "mock_sign",
            },
        }

    monkeypatch.setattr("app.api.billing.create_payment_session", _mock_create_payment_session)

    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800006667", nickname="u4b", credits=0, wechat_openid_mp="mp_openid_u4b")
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechatpay_v3",
                "test_mode": False,
                "app_id": "wx123",
                "merchant_id": "1900000109",
                "merchant_serial_no": "SERIAL001",
                "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                "api_v3_key": "12345678901234567890123456789012",
                "notify_url": "https://example.com",
            },
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post(
            "/api/v1/billing/create-order",
            json={"package_name": package_name, "provider": "wechat", "scene": "miniprogram"},
        )
        assert create_resp.status_code == 200
        data = create_resp.json()["data"]
        assert data["scene"] == "miniprogram"
        assert isinstance(data["payment_params"], dict)
        assert data["payment_params"]["package"].startswith("prepay_id=")
        assert data["qrcode_data_url"] == ""
        assert captured.get("scene") == "miniprogram"
        assert captured.get("wechat_openid") == "mp_openid_u4b"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_create_order_for_miniprogram_requires_openid(
    client: TestClient,
    db_session: Session,
) -> None:
    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800006668", nickname="u4c", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechatpay_v3",
                "test_mode": False,
                "app_id": "wx123",
                "merchant_id": "1900000109",
                "merchant_serial_no": "SERIAL001",
                "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                "api_v3_key": "12345678901234567890123456789012",
                "notify_url": "https://example.com",
            },
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.post(
            "/api/v1/billing/create-order",
            json={"package_name": package_name, "provider": "wechat", "scene": "miniprogram"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == 4216
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_create_payment_session_builds_wechat_miniprogram_params(
    db_session: Session,
    monkeypatch,
) -> None:
    class _MockResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"prepay_id": "wx_prepay_test_001"}

    monkeypatch.setattr("app.services.payment_service.httpx.post", lambda *args, **kwargs: _MockResponse())
    monkeypatch.setattr("app.services.payment_service._sign_rsa_sha256_base64", lambda *_args, **_kwargs: "mock_sign")

    user = User(phone="13800006669", nickname="u4d", credits=0, wechat_openid_mp="mp_openid_u4d")
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechatpay_v3",
                "test_mode": False,
                "app_id": "wx123456789",
                "merchant_id": "1900000109",
                "merchant_serial_no": "SERIAL001",
                "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nmock\n-----END PRIVATE KEY-----",
                "api_v3_key": "12345678901234567890123456789012",
                "notify_url": "https://example.com",
            },
            updated_by=1,
        )
    )
    db_session.flush()

    order = Order(
        order_no="GW202604060001",
        user_id=user.id,
        amount_cny=9.9,
        credits=10000,
        source="miniapp",
        status="created",
        provider="wechat",
        is_first_pay=False,
    )
    db_session.add(order)
    db_session.flush()

    session = create_payment_session(
        db_session,
        order=order,
        package_name="test_pack",
        scene="miniprogram",
        wechat_openid=user.wechat_openid_mp,
    )
    assert session["provider"] == "wechat"
    assert session["scene"] == "miniprogram"
    params = session["payment_params"]
    assert params["package"].startswith("prepay_id=")
    assert params["signType"] == "RSA"
    assert params["paySign"]


def test_payment_mock_provider_switch_between_non_prod_and_prod(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.config import get_settings

    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]
    user = User(phone="13800007777", nickname="u5", credits=0)
    db_session.add(user)
    payment_cfg = SystemConfig(
        category="system",
        config_key="payment",
        config_value={"provider": "mock", "test_mode": True},
        updated_by=1,
    )
    db_session.add(payment_cfg)
    db_session.commit()
    db_session.refresh(user)

    settings = get_settings()
    old_env = settings.app_env
    app.dependency_overrides[current_user] = lambda: user
    try:
        ok_resp = client.post("/api/v1/billing/create-order", json={"package_name": package_name, "provider": "mock"})
        assert ok_resp.status_code == 200

        payment_cfg.config_value = {"provider": "wechatpay_v3", "test_mode": False}
        db_session.commit()

        settings.app_env = "dev"
        fallback_resp = client.post("/api/v1/billing/create-order", json={"package_name": package_name, "provider": "mock"})
        assert fallback_resp.status_code == 200

        settings.app_env = "prod"
        deny_resp = client.post("/api/v1/billing/create-order", json={"package_name": package_name, "provider": "mock"})
        assert deny_resp.status_code == 400
    finally:
        settings.app_env = old_env
        app.dependency_overrides.pop(current_user, None)


def test_packages_returns_mock_provider_when_real_channel_not_ready_in_non_prod(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.config import get_settings

    user = User(phone="13800007778", nickname="u5b", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={"provider": "alipay", "test_mode": False},
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    settings = get_settings()
    old_env = settings.app_env
    settings.app_env = "dev"
    app.dependency_overrides[current_user] = lambda: user
    try:
        pkg_resp = client.get("/api/v1/billing/packages")
        assert pkg_resp.status_code == 200
        providers = pkg_resp.json()["data"]["supported_providers"]
        assert providers == ["mock"]
    finally:
        settings.app_env = old_env
        app.dependency_overrides.pop(current_user, None)


def test_create_order_fallbacks_to_mock_when_real_channel_errors_in_non_prod(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from app.config import get_settings

    package_name = DEFAULT_BILLING_PACKAGES[0]["name"]

    def _mock_channel_error(*_args, **_kwargs):
        raise BizError(code=4214, message="channel unavailable")

    monkeypatch.setattr("app.api.billing.create_payment_session", _mock_channel_error)

    user = User(phone="13800007779", nickname="u5c", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "alipay",
                "test_mode": False,
                "app_id": "2026000111111111",
                "notify_url": "https://pay.example.com/callback/alipay",
                "app_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nxyz\n-----END PUBLIC KEY-----",
            },
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    settings = get_settings()
    old_env = settings.app_env
    settings.app_env = "dev"
    app.dependency_overrides[current_user] = lambda: user
    try:
        resp = client.post(
            "/api/v1/billing/create-order",
            json={"package_name": package_name, "provider": "alipay"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["provider_requested"] == "alipay"
        assert data["provider"] == "mock"
        assert data["provider_fallback"] is True

        row = db_session.query(Order).filter(Order.order_no == data["order_no"]).first()
        assert row is not None
        assert row.provider == "mock"
    finally:
        settings.app_env = old_env
        app.dependency_overrides.pop(current_user, None)


def test_billing_packages_comes_from_admin_billing_config(
    client: TestClient,
    db_session: Session,
) -> None:
    user = User(phone="13800008888", nickname="u6", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="billing",
            config_value={
                "aigc_rate": 1,
                "dedup_rate": 2,
                "rewrite_rate": 2,
                "packages": [
                    {
                        "name": "ops_pack",
                        "price": 19.9,
                        "credits": 28000,
                        "description": "campaign package",
                        "badge": "limited",
                        "enabled": True,
                    },
                    {
                        "name": "disabled_pack",
                        "price": 99.0,
                        "credits": 99999,
                        "enabled": False,
                    },
                ],
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={"provider": "mock", "test_mode": True},
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    app.dependency_overrides[current_user] = lambda: user
    try:
        pkg_resp = client.get("/api/v1/billing/packages")
        assert pkg_resp.status_code == 200
        items = pkg_resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["name"] == "ops_pack"
        assert items[0]["description"] == "campaign package"

        order_resp = client.post(
            "/api/v1/billing/create-order",
            json={"package_name": "ops_pack", "provider": "mock"},
        )
        assert order_resp.status_code == 200
        data = order_resp.json()["data"]
        assert data["amount_cny"] == 19.9
        assert data["credits"] == 28000
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_unknown_error_handler_hides_internal_exception_detail(
    db_session: Session,
    monkeypatch,
) -> None:
    def _boom(*_args, **_kwargs):
        raise RuntimeError("LEAK_TEST_SECRET")

    monkeypatch.setattr("app.api.billing.create_payment_session", _boom)

    user = User(phone="13800009999", nickname="u7", credits=0)
    db_session.add(user)
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "wechatpay_v3",
                "test_mode": False,
                "app_id": "wx123",
                "merchant_id": "1900000109",
                "merchant_serial_no": "SERIAL001",
                "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                "api_v3_key": "12345678901234567890123456789012",
                "notify_url": "https://example.com",
            },
            updated_by=1,
        )
    )
    db_session.commit()
    db_session.refresh(user)

    def override_db():
        yield db_session

    startup_handlers = list(app.router.on_startup)
    shutdown_handlers = list(app.router.on_shutdown)
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()
    app.dependency_overrides[db_dep] = override_db
    app.dependency_overrides[current_user] = lambda: user
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/billing/create-order",
                json={"package_name": DEFAULT_BILLING_PACKAGES[0]["name"], "provider": "wechat"},
            )
            assert resp.status_code == 500
            body = resp.json()
            assert body["code"] == 5000
            assert "LEAK_TEST_SECRET" not in resp.text
    finally:
        app.dependency_overrides.pop(current_user, None)
        app.dependency_overrides.pop(db_dep, None)
        app.router.on_startup.extend(startup_handlers)
        app.router.on_shutdown.extend(shutdown_handlers)
