from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import PromoBenefitRecord, PromoBenefitType, PromoClassroom, PromoShareSubmission, ReferralRelation, User


def _send_code_and_get_debug_code(client: TestClient, phone: str, *, ip: str = "10.20.30.40") -> str:
    resp = client.post("/api/v1/auth/send-code", json={"phone": phone}, headers={"x-forwarded-for": ip})
    assert resp.status_code == 200
    return str(resp.json()["data"]["debug_code"])


def test_promo_center_tracks_invite_and_claims(client: TestClient, db_session: Session) -> None:
    inviter_code = _send_code_and_get_debug_code(client, "13800009101", ip="10.20.30.41")
    inviter_login = client.post("/api/v1/auth/login", json={"phone": "13800009101", "code": inviter_code})
    assert inviter_login.status_code == 200
    inviter_id = int(inviter_login.json()["data"]["user"]["id"])
    inviter = db_session.get(User, inviter_id)
    assert inviter is not None

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: inviter
    try:
      center_resp = client.get("/api/v1/users/me/promo-center", headers={"x-forwarded-host": "example.com"})
      assert center_resp.status_code == 200
      invite_code = center_resp.json()["data"]["invite"]["invite_code"]
      claim_resp = client.post("/api/v1/users/me/promo-center/subsidy/claim", json={"task_key": "wechat"})
      assert claim_resp.status_code == 200
    finally:
      app.dependency_overrides.pop(current_user, None)

    invitee_code = _send_code_and_get_debug_code(client, "13800009102", ip="10.20.30.42")
    invitee_login = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800009102", "code": invitee_code, "referrer_code": invite_code},
    )
    assert invitee_login.status_code == 200

    relation = db_session.query(ReferralRelation).filter(ReferralRelation.inviter_id == inviter.id).first()
    assert relation is not None
    benefit = (
        db_session.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == inviter.id, PromoBenefitRecord.scene == "invite_login")
        .first()
    )
    assert benefit is not None


def test_promo_classroom_and_share_submission_flow(client: TestClient, db_session: Session, admin_override) -> None:
    code = _send_code_and_get_debug_code(client, "13800009111", ip="10.20.30.51")
    login = client.post("/api/v1/auth/login", json={"phone": "13800009111", "code": code})
    assert login.status_code == 200
    user = db_session.get(User, int(login.json()["data"]["user"]["id"]))
    assert user is not None

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: user
    try:
        create_resp = client.post("/api/v1/users/me/promo-center/classrooms", json={"name": "格物实验班"})
        assert create_resp.status_code == 200
        share_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/1",
                "account_name": "douyin_user",
                "real_name": "张三",
                "note": "点赞已超过 20",
            },
        )
        assert share_resp.status_code == 200
        submission_id = int(share_resp.json()["data"]["id"])
    finally:
        app.dependency_overrides.pop(current_user, None)

    classroom = db_session.query(PromoClassroom).filter(PromoClassroom.owner_user_id == user.id).first()
    assert classroom is not None
    submission = db_session.get(PromoShareSubmission, submission_id)
    assert submission is not None
    assert submission.payout_account == "douyin_user"
    assert submission.payout_name == "张三"

    review_resp = client.post(
        f"/api/v1/admin/referrals/share-tasks/{submission_id}/review",
        json={"status": "approved", "review_note": "审核通过"},
    )
    assert review_resp.status_code == 200

    benefit = (
        db_session.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == user.id, PromoBenefitRecord.scene == "share_center")
        .first()
    )
    assert benefit is not None
    assert benefit.benefit_type == PromoBenefitType.CASH
    assert float(benefit.amount_cny) == 20.0
    assert benefit.payout_status == "pending"

    payout_resp = client.post(
        f"/api/v1/admin/referrals/share-tasks/{submission_id}/payout",
        json={"payout_note": "已完成人工打款"},
    )
    assert payout_resp.status_code == 200

    db_session.refresh(benefit)
    assert benefit.payout_status == "paid"
    assert benefit.paid_by is not None
    assert benefit.paid_at is not None
