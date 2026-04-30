from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditTransaction, CreditType, PromoBenefitRecord, PromoShareSubmission, ReferralRelation, SystemConfig, User, UserInviteCode, UserShareTaskSubmission
from app.security import create_token


def _auth_headers(user_id: int) -> dict[str, str]:
    token = create_token(str(user_id), "user")
    return {"Authorization": f"Bearer {token}"}


def _create_user(db_session: Session, *, user_id: int, phone: str, nickname: str) -> User:
    user = User(id=user_id, phone=phone, nickname=nickname, credits=0, source="web", is_banned=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_bind_invite_code_success(client: TestClient, db_session: Session) -> None:
    inviter = _create_user(db_session, user_id=101, phone="13800001001", nickname="邀请人")
    invitee = _create_user(db_session, user_id=102, phone="13800001002", nickname="被邀请人")
    db_session.add(UserInviteCode(user_id=inviter.id, invite_code="ABCD1234"))
    db_session.commit()

    resp = client.post(
        "/api/v1/users/me/invite/bind",
        json={"invite_code": "ABCD1234"},
        headers=_auth_headers(invitee.id),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]["bound_relation"]
    assert data["invite_code"] == "ABCD1234"
    assert data["inviter_user_id"] == inviter.id
    summary = resp.json()["data"]["invite_summary"]
    assert summary["invitee_bind_reward_granted"] is True
    assert summary["total_reward_points"] == 2000

    relation = db_session.query(ReferralRelation).filter(ReferralRelation.invitee_id == invitee.id).first()
    assert relation is not None
    assert relation.inviter_id == inviter.id
    assert relation.register_reward_sent is True

    db_session.refresh(inviter)
    db_session.refresh(invitee)
    assert inviter.credits == 1000
    assert invitee.credits == 2000

    benefits = db_session.query(PromoBenefitRecord).order_by(PromoBenefitRecord.id.asc()).all()
    assert len(benefits) == 2
    assert {row.title for row in benefits} == {"邀请绑定奖励", "有效邀请奖励"}

    tx_rows = (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.tx_type == CreditType.SHARE_REWARD)
        .order_by(CreditTransaction.id.asc())
        .all()
    )
    assert len(tx_rows) == 2
    assert [row.delta for row in tx_rows] == [2000, 1000]


def test_bind_invite_code_rejects_self_code(client: TestClient, db_session: Session) -> None:
    user = _create_user(db_session, user_id=103, phone="13800001003", nickname="自己")
    db_session.add(UserInviteCode(user_id=user.id, invite_code="SELF0001"))
    db_session.commit()

    resp = client.post(
        "/api/v1/users/me/invite/bind",
        json={"invite_code": "SELF0001"},
        headers=_auth_headers(user.id),
    )
    assert resp.status_code == 400
    assert "不能绑定自己的邀请码" in resp.json()["message"]


def test_bind_invite_code_rejects_rebinding(client: TestClient, db_session: Session) -> None:
    inviter = _create_user(db_session, user_id=104, phone="13800001004", nickname="邀请人A")
    invitee = _create_user(db_session, user_id=105, phone="13800001005", nickname="被邀请人A")
    db_session.add(UserInviteCode(user_id=inviter.id, invite_code="AGAIN001"))
    db_session.add(
        ReferralRelation(
            inviter_id=inviter.id,
            invitee_id=invitee.id,
            invite_code="AGAIN001",
            source="web",
            status="registered",
        )
    )
    db_session.commit()

    resp = client.post(
        "/api/v1/users/me/invite/bind",
        json={"invite_code": "AGAIN001"},
        headers=_auth_headers(invitee.id),
    )
    assert resp.status_code == 400
    assert "已绑定邀请码" in resp.json()["message"]


def test_bind_invite_code_grants_milestone_reward_once(client: TestClient, db_session: Session) -> None:
    inviter = _create_user(db_session, user_id=108, phone="13800001008", nickname="里程碑邀请人")
    first_invitee = _create_user(db_session, user_id=109, phone="13800001009", nickname="被邀请人1")
    second_invitee = _create_user(db_session, user_id=110, phone="13800001010", nickname="被邀请人2")
    db_session.add(UserInviteCode(user_id=inviter.id, invite_code="MILE0001"))
    db_session.add(
        SystemConfig(
            category="system",
            config_key="promo_center",
            config_value={
                "reward_rules": {
                    "invite": {
                        "invitee_bind_reward_points": 200,
                        "inviter_valid_invite_reward_points": 100,
                        "milestones": [
                            {"threshold": 2, "reward_points": 300, "label": "邀请满 2 人"},
                        ],
                    }
                }
            },
        )
    )
    db_session.commit()

    first_resp = client.post(
        "/api/v1/users/me/invite/bind",
        json={"invite_code": "MILE0001"},
        headers=_auth_headers(first_invitee.id),
    )
    assert first_resp.status_code == 200

    second_resp = client.post(
        "/api/v1/users/me/invite/bind",
        json={"invite_code": "MILE0001"},
        headers=_auth_headers(second_invitee.id),
    )
    assert second_resp.status_code == 200

    db_session.refresh(inviter)
    db_session.refresh(first_invitee)
    db_session.refresh(second_invitee)
    assert inviter.credits == 500
    assert first_invitee.credits == 200
    assert second_invitee.credits == 200

    milestone_benefits = (
        db_session.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == inviter.id, PromoBenefitRecord.title == "邀请满 2 人")
        .all()
    )
    assert len(milestone_benefits) == 1

    invite_benefits = (
        db_session.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.scene == "invite")
        .order_by(PromoBenefitRecord.id.asc())
        .all()
    )
    assert len(invite_benefits) == 5

    invite_info = client.get("/api/v1/users/me/invite", headers=_auth_headers(inviter.id))
    assert invite_info.status_code == 200
    summary = invite_info.json()["data"]["invite_summary"]
    assert summary["valid_invite_count"] == 2
    assert summary["inviter_reward_points_total"] == 200
    assert summary["milestone_reward_points_total"] == 300
    assert summary["total_reward_points"] == 500
    assert len(summary["earned_milestones"]) == 1
    assert summary["earned_milestones"][0]["threshold"] == 2


def test_submit_like_submission_and_list(client: TestClient, db_session: Session) -> None:
    user = _create_user(db_session, user_id=106, phone="13800001006", nickname="截图用户")
    file_bytes = b"fake-image-binary"

    submit = client.post(
        "/api/v1/users/me/promo/like-submissions",
        data={"platform": "wechat", "share_text": "测试文案"},
        files={"screenshot": ("proof.png", file_bytes, "image/png")},
        headers=_auth_headers(user.id),
    )
    assert submit.status_code == 200
    item = submit.json()["data"]["item"]
    assert item["platform"] == "wechat"
    assert item["status"] == "pending"
    assert item["original_filename"] == "proof.png"

    row = db_session.query(UserShareTaskSubmission).filter(UserShareTaskSubmission.user_id == user.id).first()
    assert row is not None
    assert Path(str(row.screenshot_path)).name

    listing = client.get("/api/v1/users/me/promo/like-submissions", headers=_auth_headers(user.id))
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["platform"] == "wechat"


def test_submit_like_submission_accepts_miniprogram_temp_filename_with_explicit_name(
    client: TestClient, db_session: Session
) -> None:
    user = _create_user(db_session, user_id=108, phone="13800001008", nickname="截图临时名用户")
    file_bytes = b"fake-image-binary"

    submit = client.post(
        "/api/v1/users/me/promo/like-submissions",
        data={
            "platform": "wechat",
            "share_text": "测试文案",
            "screenshot_name": "proof.png",
        },
        files={"screenshot": ("wxfile://tmp_1710000000001", file_bytes, "image/png")},
        headers=_auth_headers(user.id),
    )
    assert submit.status_code == 200
    item = submit.json()["data"]["item"]
    assert item["original_filename"] == "proof.png"

    row = db_session.query(UserShareTaskSubmission).filter(UserShareTaskSubmission.user_id == user.id).first()
    assert row is not None
    assert row.original_filename == "proof.png"
    assert Path(str(row.screenshot_path)).name.endswith("_proof.png")


def test_submit_create_submission_and_list(client: TestClient, db_session: Session) -> None:
    user = _create_user(db_session, user_id=107, phone="13800001007", nickname="创作用户")

    submit = client.post(
        "/api/v1/users/me/promo/create-submissions",
        json={
            "platform": "xiaohongshu",
            "tier_key": "tier-100",
            "share_link": "https://example.com/note/123",
            "payout_account": "alice@example.com",
            "payout_name": "Alice",
            "note": "首篇作品",
        },
        headers=_auth_headers(user.id),
    )
    assert submit.status_code == 200
    item = submit.json()["data"]["item"]
    assert item["platform"] == "xiaohongshu"
    assert item["status"] == "submitted"
    assert item["share_link"] == "https://example.com/note/123"

    row = db_session.query(PromoShareSubmission).filter(PromoShareSubmission.user_id == user.id).first()
    assert row is not None
    assert row.tier_key == "tier-100"

    listing = client.get("/api/v1/users/me/promo/create-submissions", headers=_auth_headers(user.id))
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["platform"] == "xiaohongshu"
