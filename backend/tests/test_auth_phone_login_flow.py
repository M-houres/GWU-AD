from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditTransaction, CreditType, Notification, SystemConfig, Task, User
from app.security import create_token


def _send_code_and_get_debug_code(client: TestClient, phone: str, *, ip: str = "10.10.10.10") -> str:
    resp = client.post(
        "/api/v1/auth/send-code",
        json={"phone": phone},
        headers={"x-forwarded-for": ip, "user-agent": "pytest-auth"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["debug_code"])


def test_auth_options_follow_runtime_login_config(client: TestClient, db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "sms_provider": "disabled",
                "debug_code_enabled": False,
                "wechat_login_enabled": True,
                "wechat_app_id": "wx_web_app",
                "wechat_app_secret": "wx_web_secret",
                "wechat_redirect_uri": "https://example.com/auth/wx/callback",
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx_mini_app",
                "wechat_miniprogram_app_secret": "wx_mini_secret",
                "new_user_initial_credits": 3456,
                "header_notice_text": "测试头部公告",
                "notice_enabled": True,
                "notice_title": "登录公告",
                "notice_content": "登录公告内容",
                "notice_level": "warning",
                "notice_version": 9,
                "notice_updated_at": "2026-04-11T09:00:00Z",
            },
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/auth/options")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["phone_login_enabled"] is False
    assert data["wechat_login_enabled"] is True
    assert data["wechat_miniprogram_login_enabled"] is True
    assert data["wechat_miniprogram_phone_quick_login_enabled"] is True
    assert data["new_user_initial_credits"] == 3456
    assert data["header_notice_text"] == "测试头部公告"
    assert data["notice"]["title"] == "登录公告"
    assert data["notice"]["content"] == "登录公告内容"
    assert data["notice"]["level"] == "warning"
    assert data["notice"]["version"] == 9
    assert data["notice"]["updated_at"] == "2026-04-11T09:00:00Z"


def test_auth_options_filters_mojibake_miniapp_runtime_copy(client: TestClient, db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="miniapp",
            config_value={
                "runtime_copy": {
                    "login": {
                        "brand_name": "æ ¼ç‰©å­¦æœ¯",
                        "prefer_phone_title": "è¯·ä½¿ç”¨æ‰‹æœºå·å¿«æ·ç™»å½•",
                    },
                    "home": {
                        "hero_title": "æ ¼ç‰©å­¦æœ¯",
                    },
                    "profile": {
                        "guest_login_button_text": "åŽ»ç™»å½•",
                    },
                }
            },
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/auth/options")
    assert resp.status_code == 200
    runtime = resp.json()["data"]["miniapp_runtime"]
    assert runtime["login"]["brand_name"] == "格物学术"
    assert runtime["login"]["prefer_phone_title"] == "请使用手机号快捷登录"
    assert runtime["home"]["hero_title"] == "格物学术"
    assert runtime["profile"]["guest_login_button_text"] == "去登录"


def test_phone_login_creates_user_once_and_grants_initial_credits_once(client: TestClient, db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={"debug_code_enabled": True, "new_user_initial_credits": 3456},
        )
    )
    db_session.commit()

    phone = "13800006100"
    first_code = _send_code_and_get_debug_code(client, phone)
    first = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": first_code},
        headers={"x-forwarded-for": "10.10.10.10", "user-agent": "pytest-auth"},
    )
    assert first.status_code == 200
    first_data = first.json()["data"]
    assert first_data["is_new_user"] is True

    user_id = int(first_data["user"]["id"])
    user = db_session.get(User, user_id)
    assert user is not None
    assert user.credits == 3456

    init_rows = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id, CreditTransaction.tx_type == CreditType.INIT)
        .all()
    )
    assert len(init_rows) == 1
    assert init_rows[0].delta == 3456

    second_code = _send_code_and_get_debug_code(client, phone, ip="10.10.10.11")
    second = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": second_code},
        headers={"x-forwarded-for": "10.10.10.11", "user-agent": "pytest-auth"},
    )
    assert second.status_code == 200
    second_data = second.json()["data"]
    assert second_data["is_new_user"] is False

    db_session.refresh(user)
    assert user.credits == 3456
    init_rows = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user.id, CreditTransaction.tx_type == CreditType.INIT)
        .all()
    )
    assert len(init_rows) == 1


def test_login_wrong_code_locks_phone_after_max_retry(client: TestClient, db_session: Session) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={"debug_code_enabled": True, "max_code_retry": 2, "phone_lock_minutes": 1},
        )
    )
    db_session.commit()

    phone = "13800006101"
    _send_code_and_get_debug_code(client, phone)

    first = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": "000000"},
        headers={"x-forwarded-for": "10.10.10.12", "user-agent": "pytest-auth"},
    )
    assert first.status_code == 400
    assert first.json()["code"] == 4005

    second = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": "111111"},
        headers={"x-forwarded-for": "10.10.10.12", "user-agent": "pytest-auth"},
    )
    assert second.status_code == 400
    assert second.json()["code"] == 4005

    locked = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "code": "222222"},
        headers={"x-forwarded-for": "10.10.10.12", "user-agent": "pytest-auth"},
    )
    assert locked.status_code == 400
    assert locked.json()["code"] == 4004


def test_banned_user_token_cannot_access_user_endpoints(client: TestClient, db_session: Session) -> None:
    user = User(phone="13800006111", nickname="banned-token", credits=100, is_banned=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_token(subject=str(user.id), scope="user")
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert resp.json()["message"] == "user banned"


def test_wx_miniprogram_phone_login_merges_legacy_openid_user_into_phone_user(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx_mini_app",
                "wechat_miniprogram_app_secret": "wx_mini_secret",
            },
        )
    )
    openid_user = User(phone="19100061020", nickname="openid-user", credits=0, wechat_openid_mp="mp_openid_conflict")
    phone_user = User(phone="13800006103", nickname="phone-user", credits=0)
    db_session.add_all([openid_user, phone_user])
    db_session.commit()

    monkeypatch.setattr(
        "app.api.auth._resolve_miniprogram_openid_unionid",
        lambda *_args, **_kwargs: ("mp_openid_conflict", "union_conflict"),
    )
    monkeypatch.setattr(
        "app.api.auth._resolve_miniprogram_phone_number",
        lambda *_args, **_kwargs: "13800006103",
    )

    resp = client.post(
        "/api/v1/auth/wx/mini-phone-login",
        json={"login_code": "mock_login_code", "phone_code": "mock_phone_code"},
        headers={"x-forwarded-for": "10.10.10.13", "user-agent": "pytest-auth"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert int(body["data"]["user"]["id"]) == int(phone_user.id)

    db_session.refresh(phone_user)
    db_session.refresh(openid_user)
    assert phone_user.wechat_openid_mp == "mp_openid_conflict"
    assert openid_user.is_banned is True
    assert str(openid_user.phone).startswith("del")


def test_wx_miniprogram_phone_login_merge_transfers_legacy_assets(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    db_session.add(
        SystemConfig(
            category="system",
            config_key="login",
            config_value={
                "wechat_miniprogram_login_enabled": True,
                "wechat_miniprogram_app_id": "wx_mini_app",
                "wechat_miniprogram_app_secret": "wx_mini_secret",
            },
        )
    )
    openid_user = User(phone="19100061021", nickname="legacy-openid", credits=1200, wechat_openid_mp="mp_openid_merge")
    phone_user = User(phone="13800006104", nickname="phone-user-2", credits=300)
    db_session.add_all([openid_user, phone_user])
    db_session.commit()
    db_session.refresh(openid_user)
    db_session.refresh(phone_user)

    db_session.add_all(
        [
            Notification(user_id=openid_user.id, title="n1", content="c1"),
            Task(
                user_id=openid_user.id,
                task_type="aigc_detect",
                platform="cnki",
                source="miniprogram",
                status="completed",
                source_filename="a.txt",
                source_path="/tmp/a.txt",
            ),
            CreditTransaction(
                user_id=openid_user.id,
                tx_type=CreditType.SHARE_REWARD,
                delta=100,
                balance_before=1100,
                balance_after=1200,
                reason="legacy",
                related_id="legacy:merge:1",
                source="miniprogram",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.api.auth._resolve_miniprogram_openid_unionid",
        lambda *_args, **_kwargs: ("mp_openid_merge", "union_merge"),
    )
    monkeypatch.setattr(
        "app.api.auth._resolve_miniprogram_phone_number",
        lambda *_args, **_kwargs: "13800006104",
    )

    resp = client.post(
        "/api/v1/auth/wx/mini-phone-login",
        json={"login_code": "mock_login_code2", "phone_code": "mock_phone_code2"},
        headers={"x-forwarded-for": "10.10.10.14", "user-agent": "pytest-auth"},
    )
    assert resp.status_code == 200

    transferred_notification = db_session.query(Notification).filter(Notification.user_id == phone_user.id).first()
    transferred_task = db_session.query(Task).filter(Task.user_id == phone_user.id).first()
    transferred_tx = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.user_id == phone_user.id, CreditTransaction.related_id == "legacy:merge:1")
        .first()
    )

    assert transferred_notification is not None
    assert transferred_task is not None
    assert transferred_tx is not None
