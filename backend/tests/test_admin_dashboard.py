from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    LLMErrorLog,
    CreditTransaction,
    CreditType,
    Order,
    SystemConfig,
    Task,
    TaskStatus,
    TaskType,
    User,
)


def test_admin_dashboard_returns_mvp_baseline_and_operational_alerts(
    client: TestClient,
    db_session: Session,
    admin_override,
) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "sms_provider": "custom_webhook",
                "sms_gateway_url": "https://sms.example.com/send",
                "debug_code_enabled": False,
                "wechat_login_enabled": False,
                "wechat_miniprogram_login_enabled": False,
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="payment",
            config_value={
                "provider": "mock",
                "test_mode": True,
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="billing",
            config_value={
                "aigc_points_per_char": 1,
                "dedup_points_per_char": 1,
                "rewrite_points_per_char": 1,
                "packages": [{"name": "MVP 包", "price": 19, "credits": 10000, "enabled": True}],
            },
            updated_by=1,
        )
    )
    db_session.add(
        SystemConfig(
            category="system",
            config_key="miniapp",
            config_value={
                "enabled": True,
                "app_id": "wx-mini-001",
                "app_secret": "mini-secret-001",
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx-mini-001",
                "wechat_miniprogram_app_secret": "mini-secret-001",
                "api_base_url": "https://api.example.com/api/v1",
                "request_domain": "https://api.example.com",
                "wechat_miniprogram_payment_enabled": True,
                "payment_notify_url": "https://pay.example.com/api/v1/billing/notify/wechatpay",
            },
            updated_by=1,
        )
    )

    user = User(phone="13800005555", nickname="dashboard-user", credits=9000, source="miniprogram")
    db_session.add(user)
    db_session.flush()

    db_session.add(
        CreditTransaction(
            user_id=user.id,
            tx_type=CreditType.PACKAGE_PAY,
            delta=10000,
            balance_before=0,
            balance_after=10000,
            reason="充值",
            related_id="GW-DASH-ORDER-1",
            source="miniprogram",
        )
    )
    db_session.add(
        Order(
            order_no="GW-DASH-ORDER-1",
            user_id=user.id,
            amount_cny=19,
            credits=10000,
            source="miniprogram",
            status="paid",
            provider="mock",
            is_first_pay=True,
        )
    )
    db_session.add(
        Task(
            user_id=user.id,
            task_type=TaskType.AIGC_DETECT,
            platform="cnki",
            status=TaskStatus.FAILED,
            source="miniprogram",
            source_filename="a.docx",
            source_path="/tmp/a.docx",
            char_count=1000,
            cost_credits=1000,
            refund_done=False,
            error_message="算法执行失败",
            created_at=datetime.utcnow(),
        )
    )
    db_session.add(
        LLMErrorLog(
            task_id=None,
            error_type="timeout",
            error_detail="llm timeout",
            trigger_downgrade=True,
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/admin/dashboard")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["overview"]["total_users"] >= 1
    assert data["source_stats"]["tasks"]["miniapp"] >= 1
    assert data["source_stats"]["paid_orders"]["miniapp"] >= 1

    baseline = data["mvp_baseline"]
    assert baseline["status"] == "warning"
    assert isinstance(baseline["items"], list)
    assert any(item["key"] == "payment" and item["status"] == "warning" for item in baseline["items"])
    assert any(item["key"] == "miniapp" and item["status"] == "ready" for item in baseline["items"])

    alerts = data["operational_alerts"]
    assert any(item["key"] == "failed_tasks" for item in alerts)
    assert any(item["key"] == "refund_pending" for item in alerts)
    assert any(item["key"] == "payment_mode" for item in alerts)
    assert any(item["key"] == "llm_errors" for item in alerts)

    ops_summary = data["ops_summary"]
    assert ops_summary["task_status"]["failed"] >= 1
    assert ops_summary["refund_pending_count"] >= 1
    assert ops_summary["llm_error_24h"] >= 1
