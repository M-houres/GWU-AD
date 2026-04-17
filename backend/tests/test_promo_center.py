from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import PromoBenefitRecord, PromoBenefitType, PromoClassroom, PromoClassroomMember, PromoShareSubmission, ReferralRelation, User


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
        duplicate_submit_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/1-dup",
                "account_name": "douyin_user",
                "real_name": "张三",
                "note": "重复提交",
            },
        )
        assert duplicate_submit_resp.status_code == 409
        assert duplicate_submit_resp.json()["code"] == 4418
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

    app.dependency_overrides[current_user] = lambda: user
    try:
        center_after_approved_resp = client.get("/api/v1/users/me/promo-center")
        assert center_after_approved_resp.status_code == 200
        share_platforms = center_after_approved_resp.json()["data"]["share_center"]["platforms"]
        douyin_platform = next(item for item in share_platforms if item["key"] == "douyin")
        assert douyin_platform["status"] == "approved"
        assert douyin_platform["can_submit"] is False

        approved_resubmit_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/approved-resubmit",
                "account_name": "douyin_user",
                "real_name": "张三",
                "note": "审核通过后重提",
            },
        )
        assert approved_resubmit_resp.status_code == 409
        assert approved_resubmit_resp.json()["code"] == 4420
    finally:
        app.dependency_overrides.pop(current_user, None)

    payout_resp = client.post(
        f"/api/v1/admin/referrals/share-tasks/{submission_id}/payout",
        json={"payout_note": "已完成人工打款"},
    )
    assert payout_resp.status_code == 200

    db_session.refresh(benefit)
    assert benefit.payout_status == "paid"
    assert benefit.paid_by is not None
    assert benefit.paid_at is not None

    app.dependency_overrides[current_user] = lambda: user
    try:
        center_after_paid_resp = client.get("/api/v1/users/me/promo-center")
        assert center_after_paid_resp.status_code == 200
        share_platforms = center_after_paid_resp.json()["data"]["share_center"]["platforms"]
        douyin_platform = next(item for item in share_platforms if item["key"] == "douyin")
        assert douyin_platform["status"] == "paid"
        assert douyin_platform["can_submit"] is False

        paid_resubmit_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/paid-resubmit",
                "account_name": "douyin_user",
                "real_name": "张三",
                "note": "打款后重提",
            },
        )
        assert paid_resubmit_resp.status_code == 409
        assert paid_resubmit_resp.json()["code"] == 4421
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_promo_share_rejected_can_resubmit(client: TestClient, db_session: Session, admin_override) -> None:
    code = _send_code_and_get_debug_code(client, "13800009131", ip="10.20.30.71")
    login = client.post("/api/v1/auth/login", json={"phone": "13800009131", "code": code})
    assert login.status_code == 200
    user = db_session.get(User, int(login.json()["data"]["user"]["id"]))
    assert user is not None

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: user
    try:
        first_submit_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "weibo",
                "tier_key": "boost",
                "share_link": "https://example.com/share/weibo/1",
                "account_name": "weibo_user",
                "real_name": "李四",
                "note": "第一次提交",
            },
        )
        assert first_submit_resp.status_code == 200
        submission_id = int(first_submit_resp.json()["data"]["id"])
    finally:
        app.dependency_overrides.pop(current_user, None)

    reject_resp = client.post(
        f"/api/v1/admin/referrals/share-tasks/{submission_id}/review",
        json={"status": "rejected", "review_note": "内容不完整"},
    )
    assert reject_resp.status_code == 200

    app.dependency_overrides[current_user] = lambda: user
    try:
        resubmit_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "weibo",
                "tier_key": "top",
                "share_link": "https://example.com/share/weibo/2",
                "account_name": "weibo_user_new",
                "real_name": "李四",
                "note": "修正后再次提交",
            },
        )
        assert resubmit_resp.status_code == 200
        assert int(resubmit_resp.json()["data"]["id"]) == submission_id
    finally:
        app.dependency_overrides.pop(current_user, None)

    submission = db_session.get(PromoShareSubmission, submission_id)
    assert submission is not None
    assert submission.status.value == "submitted"
    assert submission.share_link == "https://example.com/share/weibo/2"
    assert submission.payout_account == "weibo_user_new"
    assert submission.review_note is None
    assert submission.reviewed_by is None
    assert submission.reviewed_at is None


def test_promo_share_submission_validation_errors(client: TestClient, db_session: Session) -> None:
    code = _send_code_and_get_debug_code(client, "13800009121", ip="10.20.30.61")
    login = client.post("/api/v1/auth/login", json={"phone": "13800009121", "code": code})
    assert login.status_code == 200
    user = db_session.get(User, int(login.json()["data"]["user"]["id"]))
    assert user is not None

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: user
    try:
        invalid_link_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "not-a-url",
                "account_name": "18800001111",
                "real_name": "张三",
                "note": "平台昵称：测试账号",
            },
        )
        assert invalid_link_resp.status_code == 422
        assert invalid_link_resp.json()["code"] == 4415

        missing_account_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/2",
                "account_name": "",
                "real_name": "张三",
                "note": "平台昵称：测试账号",
            },
        )
        assert missing_account_resp.status_code == 422
        assert missing_account_resp.json()["code"] == 4416

        missing_name_resp = client.post(
            "/api/v1/users/me/promo-center/shares",
            json={
                "platform": "douyin",
                "tier_key": "top",
                "share_link": "https://example.com/share/douyin/2",
                "account_name": "18800001111",
                "real_name": "",
                "note": "平台昵称：测试账号",
            },
        )
        assert missing_name_resp.status_code == 422
        assert missing_name_resp.json()["code"] == 4417
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_promo_classroom_rejects_multi_class_membership(client: TestClient, db_session: Session) -> None:
    owner_a_code = _send_code_and_get_debug_code(client, "13800009201", ip="10.20.31.01")
    owner_a_login = client.post("/api/v1/auth/login", json={"phone": "13800009201", "code": owner_a_code})
    assert owner_a_login.status_code == 200
    owner_a = db_session.get(User, int(owner_a_login.json()["data"]["user"]["id"]))
    assert owner_a is not None

    owner_b_code = _send_code_and_get_debug_code(client, "13800009202", ip="10.20.31.02")
    owner_b_login = client.post("/api/v1/auth/login", json={"phone": "13800009202", "code": owner_b_code})
    assert owner_b_login.status_code == 200
    owner_b = db_session.get(User, int(owner_b_login.json()["data"]["user"]["id"]))
    assert owner_b is not None

    member_code = _send_code_and_get_debug_code(client, "13800009203", ip="10.20.31.03")
    member_login = client.post("/api/v1/auth/login", json={"phone": "13800009203", "code": member_code})
    assert member_login.status_code == 200
    member = db_session.get(User, int(member_login.json()["data"]["user"]["id"]))
    assert member is not None

    from app.deps import current_user

    app.dependency_overrides[current_user] = lambda: owner_a
    try:
        create_a_resp = client.post("/api/v1/users/me/promo-center/classrooms", json={"name": "A班"})
        assert create_a_resp.status_code == 200
        invite_code_a = str(create_a_resp.json()["data"]["invite_code"])
    finally:
        app.dependency_overrides.pop(current_user, None)

    app.dependency_overrides[current_user] = lambda: owner_b
    try:
        create_b_resp = client.post("/api/v1/users/me/promo-center/classrooms", json={"name": "B班"})
        assert create_b_resp.status_code == 200
        invite_code_b = str(create_b_resp.json()["data"]["invite_code"])
    finally:
        app.dependency_overrides.pop(current_user, None)

    app.dependency_overrides[current_user] = lambda: member
    try:
        join_a_resp = client.post("/api/v1/users/me/promo-center/classrooms/join", json={"invite_code": invite_code_a})
        assert join_a_resp.status_code == 200
        assert join_a_resp.json()["data"]["role"] == "member"

        join_a_idempotent_resp = client.post("/api/v1/users/me/promo-center/classrooms/join", json={"invite_code": invite_code_a})
        assert join_a_idempotent_resp.status_code == 200

        join_b_resp = client.post("/api/v1/users/me/promo-center/classrooms/join", json={"invite_code": invite_code_b})
        assert join_b_resp.status_code == 409
        assert join_b_resp.json()["code"] == 4413

        create_conflict_resp = client.post("/api/v1/users/me/promo-center/classrooms", json={"name": "成员再建班"})
        assert create_conflict_resp.status_code == 409
        assert create_conflict_resp.json()["code"] == 4413
    finally:
        app.dependency_overrides.pop(current_user, None)

    memberships = (
        db_session.query(PromoClassroomMember)
        .filter(PromoClassroomMember.user_id == member.id)
        .all()
    )
    assert len(memberships) == 1
