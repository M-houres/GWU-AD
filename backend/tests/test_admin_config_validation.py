from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import SystemConfig


def _readiness_item(client: TestClient, category: str) -> dict:
    resp = client.get("/api/v1/admin/configs/readiness")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    return next(item for item in items if item["category"] == category)


def test_save_llm_config_for_domestic_provider(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/llm",
        json={
            "enabled": True,
            "provider": "qwen",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "api_key": "sk-test-qwen",
            "timeout_seconds": 30,
            "max_output_tokens": 4096,
            "temperature": 0.2,
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["provider"] == "qwen"
    assert value["model"] == "qwen-plus"

    readiness = _readiness_item(client, "llm")
    assert readiness["status"] == "ready"


def test_save_alipay_config_and_readiness_ready(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/payment",
        json={
            "provider": "alipay",
            "test_mode": False,
            "app_id": "2026000111111111",
            "gateway_url": "https://openapi.alipay.com/gateway.do",
            "notify_url": "https://pay.example.com/callback/alipay",
            "app_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nxyz\n-----END PUBLIC KEY-----",
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["provider"] == "alipay"
    assert value["api_key"].startswith("-----BEGIN PRIVATE KEY-----")

    readiness = _readiness_item(client, "payment")
    assert readiness["status"] == "ready"


def test_reject_unsupported_gateway_proxy_payment_config(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/payment",
        json={
            "provider": "gateway_proxy",
            "test_mode": False,
            "notify_url": "https://pay.example.com/callback",
        },
    )
    assert resp.status_code == 400
    assert "payment.provider" in resp.json()["message"]


def test_payment_readiness_flags_legacy_alipay_missing_public_key(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "alipay",
                "test_mode": False,
                "app_id": "2026000222222222",
                "notify_url": "https://pay.example.com/callback/alipay",
                "app_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            },
            updated_by=1,
        )
    )
    db_session.commit()

    readiness = _readiness_item(client, "payment")
    assert readiness["status"] == "error"
    assert "alipay_public_key" in readiness["message"]


def test_payment_readiness_flags_legacy_gateway_proxy_as_unsupported(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "gateway_proxy",
                "test_mode": False,
                "notify_url": "https://pay.example.com/callback",
            },
            updated_by=1,
        )
    )
    db_session.commit()

    readiness = _readiness_item(client, "payment")
    assert readiness["status"] == "error"
    assert "不支持" in readiness["message"]


def test_reject_private_notify_url_for_real_wechat_payment(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/payment",
        json={
            "provider": "wechatpay_v3",
            "test_mode": False,
            "app_id": "wx1234567890",
            "merchant_id": "1900000109",
            "merchant_serial_no": "SERIAL123456",
            "merchant_private_key_pem": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "api_v3_key": "12345678901234567890123456789012",
            "notify_url": "https://127.0.0.1:8100/api/v1/billing/notify/wechatpay",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "公网 HTTPS" in body["message"]


def test_save_billing_with_packages_affects_public_package_list(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/billing",
        json={
            "aigc_rate": 1,
            "dedup_rate": 3,
            "rewrite_rate": 4,
            "packages": [
                {
                    "name": "校园体验包",
                    "price": 29.9,
                    "credits": 42000,
                    "description": "用于毕业季密集检测",
                    "badge": "热销",
                    "enabled": True,
                },
                {
                    "name": "隐藏套餐",
                    "price": 88.0,
                    "credits": 88000,
                    "enabled": False,
                },
            ],
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["dedup_rate"] == 3
    assert len(value["packages"]) == 2

    pkg_resp = client.get("/api/v1/billing/packages")
    assert pkg_resp.status_code == 200
    items = pkg_resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "校园体验包"
    assert items[0]["credits"] == 42000


def test_save_login_strategy_config_affects_auth_options(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/login",
        json={
            "sms_provider": "disabled",
            "debug_code_enabled": True,
            "wechat_login_enabled": False,
            "wechat_miniprogram_login_enabled": True,
            "wechat_miniprogram_app_id": "wx-mini-test-001",
            "wechat_miniprogram_app_secret": "mini-secret-test-001",
            "new_user_initial_credits": 2000,
            "max_code_retry": 4,
            "phone_lock_minutes": 8,
            "send_code_ip_1h_limit": 88,
            "login_ip_10m_limit": 66,
            "notice_enabled": True,
            "notice_title": "系统维护通知",
            "notice_content": "今晚 23:00-23:30 平台将进行例行升级维护。",
            "notice_level": "important",
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["new_user_initial_credits"] == 2000
    assert value["max_code_retry"] == 4
    assert value["phone_lock_minutes"] == 8
    assert value["send_code_ip_1h_limit"] == 88
    assert value["login_ip_10m_limit"] == 66

    options = client.get("/api/v1/auth/options")
    assert options.status_code == 200
    data = options.json()["data"]
    assert data["new_user_initial_credits"] == 2000
    assert data["notice"]["title"] == "系统维护通知"
    assert data["notice"]["content"].startswith("今晚 23:00")
    assert data["notice"]["level"] == "important"
    assert data["notice"]["enabled"] is True
    assert data["notice"]["version"] >= 1
    assert data["wechat_miniprogram_login_enabled"] is True


def test_notice_version_increases_when_notice_content_changes(
    client: TestClient,
    admin_override,
) -> None:
    first = client.post(
        "/api/v1/admin/configs/login",
        json={
            "sms_provider": "disabled",
            "debug_code_enabled": True,
            "wechat_login_enabled": False,
            "notice_enabled": True,
            "notice_title": "公告",
            "notice_content": "第一版公告",
            "notice_level": "info",
        },
    )
    assert first.status_code == 200
    first_value = first.json()["data"]["value"]
    first_version = int(first_value.get("notice_version") or 1)

    second = client.post(
        "/api/v1/admin/configs/login",
        json={
            "sms_provider": "disabled",
            "debug_code_enabled": True,
            "wechat_login_enabled": False,
            "notice_enabled": True,
            "notice_title": "公告",
            "notice_content": "第二版公告",
            "notice_level": "warning",
            "notice_version": first_version,
            "notice_updated_at": first_value.get("notice_updated_at", ""),
        },
    )
    assert second.status_code == 200
    second_value = second.json()["data"]["value"]
    second_version = int(second_value.get("notice_version") or 1)
    assert second_version == first_version + 1
    assert second_value.get("notice_updated_at")

    notice_resp = client.get("/api/v1/auth/announcement")
    assert notice_resp.status_code == 200
    notice = notice_resp.json()["data"]
    assert notice["content"] == "第二版公告"
    assert notice["level"] == "warning"
    assert int(notice["version"]) == second_version


def test_save_local_mock_llm_config_without_api_key(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/llm",
        json={
            "enabled": True,
            "provider": "local_mock",
            "model": "local-mock-v1",
            "timeout_seconds": 20,
            "max_output_tokens": 1024,
            "temperature": 0.1,
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["provider"] == "local_mock"
    assert value["model"] == "local-mock-v1"
    assert value["api_key"] == ""

    readiness = _readiness_item(client, "llm")
    assert readiness["status"] == "ready"


def test_save_notice_config_in_separate_category_affects_auth_announcement(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/notice",
        json={
            "enabled": True,
            "title": "发布提醒",
            "content": "今晚 23:30 进行系统维护。",
            "header_text": "今晚 23:30 系统维护，请提前保存进度。",
            "level": "important",
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["title"] == "发布提醒"
    assert value["level"] == "important"

    ann = client.get("/api/v1/auth/announcement")
    assert ann.status_code == 200
    payload = ann.json()["data"]
    assert payload["title"] == "发布提醒"
    assert payload["level"] == "important"
    assert payload["enabled"] is True


def test_save_miniapp_config_in_separate_category_affects_auth_options(
    client: TestClient,
    admin_override,
) -> None:
    resp = client.post(
        "/api/v1/admin/configs/miniapp",
        json={
            "enabled": True,
            "app_id": "wx-mini-ops-001",
            "app_secret": "mini-secret-ops-001",
            "wechat_miniprogram_login_enabled": True,
            "wechat_miniprogram_app_id": "wx-mini-ops-001",
            "wechat_miniprogram_app_secret": "mini-secret-ops-001",
            "api_base_url": "https://api.example.com/api/v1",
            "request_domain": "https://api.example.com",
        },
    )
    assert resp.status_code == 200
    value = resp.json()["data"]["value"]
    assert value["wechat_miniprogram_login_enabled"] is True
    assert value["wechat_miniprogram_app_id"] == "wx-mini-ops-001"

    options = client.get("/api/v1/auth/options")
    assert options.status_code == 200
    data = options.json()["data"]
    assert data["wechat_miniprogram_login_enabled"] is True
