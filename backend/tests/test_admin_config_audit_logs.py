from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import AdminAuditLog, AdminUser


def test_config_audit_logs_include_changed_fields(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(AdminUser(id=1, username="admin", password_hash="x", role="super_admin"))
    db_session.commit()

    resp = client.post(
        "/api/v1/admin/configs/billing",
        json={"aigc_points_per_char": 2, "dedup_points_per_char": 6, "rewrite_points_per_char": 2},
    )
    assert resp.status_code == 200

    logs = client.get("/api/v1/admin/configs/audit-logs", params={"page": 1, "page_size": 10})
    assert logs.status_code == 200

    items = logs.json()["data"]["items"]
    assert len(items) >= 1

    first = items[0]
    assert first["admin_username"] == "admin"
    assert first["target_type"] == "billing"
    assert first["target_type_label"] == "计费规则"
    assert set(first["changed_fields"]) == {"aigc_points_per_char", "dedup_points_per_char", "rewrite_points_per_char"}
    assert first["changed_count"] == 3
    assert any("降重单价" in label for label in first["changed_field_labels"])
    assert "计费规则" in first["summary"]

    readiness = client.get("/api/v1/admin/configs/readiness")
    assert readiness.status_code == 200
    readiness_items = readiness.json()["data"]["items"]
    categories = {item["category"] for item in readiness_items}
    assert {"llm", "payment", "billing", "login", "notice", "miniapp", "user_navigation"} <= categories


def test_config_audit_logs_do_not_store_payment_secrets_in_plaintext(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(AdminUser(id=1, username="admin", password_hash="x", role="super_admin"))
    db_session.commit()

    resp = client.post(
        "/api/v1/admin/configs/payment",
        json={
            "provider": "alipay",
            "test_mode": False,
            "app_id": "2026000111111111",
            "gateway_url": "https://openapi.alipay.com/gateway.do",
            "notify_url": "https://pay.example.com/callback/alipay",
            "app_private_key_pem": "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
            "alipay_public_key": "-----BEGIN PUBLIC KEY-----\nxyz\n-----END PUBLIC KEY-----",
            "callback_secret": "callback_secret_plaintext",
        },
    )
    assert resp.status_code == 200

    audit = (
        db_session.query(AdminAuditLog)
        .filter(AdminAuditLog.action == "config_update", AdminAuditLog.target_type == "payment")
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    assert audit is not None
    assert "BEGIN PRIVATE KEY" not in str(audit.after_json)
    assert "callback_secret_plaintext" not in str(audit.after_json)
    assert audit.after_json["app_private_key_pem"] == "********"
