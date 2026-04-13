from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import current_user
from app.main import app
from app.models import ReferralRelation, User, UserInviteCode
from app.services.referral_module import REFERRAL_MODULE_DISABLED_MESSAGE


def _send_code_and_get_debug_code(client: TestClient, phone: str, *, ip: str) -> str:
    resp = client.post(
        "/api/v1/auth/send-code",
        json={"phone": phone},
        headers={"x-forwarded-for": ip, "user-agent": "pytest-referral-disabled"},
    )
    assert resp.status_code == 200
    return str(resp.json()["data"]["debug_code"])


def test_referral_endpoints_return_gone(client: TestClient, db_session: Session, admin_override) -> None:
    user = User(phone="13800008100", nickname="offline-user", credits=0)
    db_session.add(user)
    db_session.commit()

    app.dependency_overrides[current_user] = lambda: user
    try:
        user_resp = client.get("/api/v1/users/me/growth-center")
    finally:
        app.dependency_overrides.pop(current_user, None)

    admin_resp = client.get("/api/v1/admin/referrals/stats")

    assert user_resp.status_code == 410
    assert user_resp.json()["message"] == REFERRAL_MODULE_DISABLED_MESSAGE
    assert admin_resp.status_code == 410
    assert admin_resp.json()["message"] == REFERRAL_MODULE_DISABLED_MESSAGE


def test_login_with_referrer_code_no_longer_creates_referral_relation(client: TestClient, db_session: Session) -> None:
    inviter = User(phone="13800008101", nickname="inviter", credits=0)
    db_session.add(inviter)
    db_session.flush()
    db_session.add(UserInviteCode(user_id=inviter.id, invite_code="REFDIS01"))
    db_session.commit()

    invitee_code = _send_code_and_get_debug_code(client, "13800008102", ip="10.10.81.02")
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800008102", "code": invitee_code, "referrer_code": "REFDIS01"},
        headers={"x-forwarded-for": "10.10.81.02", "user-agent": "pytest-referral-disabled"},
    )

    assert login_resp.status_code == 200
    assert db_session.query(ReferralRelation).count() == 0
