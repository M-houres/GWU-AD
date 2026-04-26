from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import CreditTransaction, CreditType, PromoBenefitRecord, PromoShareSubmission, PromoShareSubmissionStatus, ShareTaskStatus, SystemConfig, User, UserShareTaskSubmission


def _seed_user(db_session: Session, *, phone: str, nickname: str) -> User:
    user = User(phone=phone, nickname=nickname, credits=0, source="web", is_banned=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_can_list_like_submissions(client: TestClient, db_session: Session, admin_override) -> None:
    user = _seed_user(db_session, phone="13800002001", nickname="like-user")
    db_session.add(
        UserShareTaskSubmission(
            user_id=user.id,
            platform="wechat",
            screenshot_path="uploads/promo/like/demo.png",
            original_filename="demo.png",
            share_text="集赞截图",
            status=ShareTaskStatus.PENDING,
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/admin/promo/like-submissions", params={"status": "pending"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status_stats"]["pending"] == 1
    assert data["items"][0]["user_phone"] == user.phone
    assert data["items"][0]["platform"] == "wechat"


def test_admin_can_review_like_submission(client: TestClient, db_session: Session, admin_override) -> None:
    user = _seed_user(db_session, phone="13800002002", nickname="like-review")
    db_session.add(
        SystemConfig(
            category="system",
            config_key="promo_center",
            config_value={
                "reward_rules": {
                    "like": {
                        "tiers": [
                            {"threshold": 10, "reward_points": 10000, "label": "10 赞"},
                            {"threshold": 20, "reward_points": 20000, "label": "20 赞"},
                        ]
                    },
                    "create": {
                        "tiers": [
                            {"threshold": 0, "reward_points": 5000, "label": "发帖即送"}
                        ]
                    },
                }
            },
        )
    )
    db_session.commit()
    row = UserShareTaskSubmission(
        user_id=user.id,
        platform="wechat",
        screenshot_path="uploads/promo/like/review.png",
        original_filename="review.png",
        share_text="待审核",
        status=ShareTaskStatus.PENDING,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    resp = client.post(
        f"/api/v1/admin/promo/like-submissions/{row.id}/review",
        json={"status": "approved", "review_note": "截图清晰", "reward_option_key": "tier-2"},
    )
    assert resp.status_code == 200
    db_session.refresh(row)
    assert row.status == ShareTaskStatus.APPROVED
    assert row.review_note == "截图清晰"
    assert row.reward_credits == 20000
    db_session.refresh(user)
    assert user.credits == 20000
    benefit = db_session.query(PromoBenefitRecord).filter(PromoBenefitRecord.user_id == user.id, PromoBenefitRecord.scene == "like").first()
    assert benefit is not None
    assert benefit.credit_delta == 20000
    tx = db_session.query(CreditTransaction).filter(CreditTransaction.user_id == user.id, CreditTransaction.tx_type == CreditType.SHARE_REWARD).first()
    assert tx is not None
    assert tx.delta == 20000

    second = client.post(
        f"/api/v1/admin/promo/like-submissions/{row.id}/review",
        json={"status": "approved", "review_note": "再次确认", "reward_option_key": "tier-2"},
    )
    assert second.status_code == 200
    tx_rows = db_session.query(CreditTransaction).filter(CreditTransaction.user_id == user.id, CreditTransaction.tx_type == CreditType.SHARE_REWARD).all()
    assert len(tx_rows) == 1

    rejected_after_grant = client.post(
        f"/api/v1/admin/promo/like-submissions/{row.id}/review",
        json={"status": "rejected", "review_note": "想撤回"},
    )
    assert rejected_after_grant.status_code == 400


def test_admin_like_review_requires_reward_option_when_approving(client: TestClient, db_session: Session, admin_override) -> None:
    user = _seed_user(db_session, phone="13800002004", nickname="like-no-tier")
    row = UserShareTaskSubmission(
        user_id=user.id,
        platform="wechat",
        screenshot_path="uploads/promo/like/no-tier.png",
        original_filename="no-tier.png",
        share_text="待审核",
        status=ShareTaskStatus.PENDING,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    resp = client.post(
        f"/api/v1/admin/promo/like-submissions/{row.id}/review",
        json={"status": "approved", "review_note": "没选档位"},
    )
    assert resp.status_code == 400


def test_admin_can_review_create_submission(client: TestClient, db_session: Session, admin_override) -> None:
    user = _seed_user(db_session, phone="13800002003", nickname="create-review")
    db_session.add(
        SystemConfig(
            category="system",
            config_key="promo_center",
            config_value={
                "reward_rules": {
                    "create": {
                        "tiers": [
                            {"threshold": 0, "reward_points": 5000, "label": "发帖即送"},
                            {"threshold": 10, "reward_points": 10000, "label": "10+ 赞"},
                        ]
                    }
                }
            },
        )
    )
    db_session.commit()
    row = PromoShareSubmission(
        user_id=user.id,
        platform="xiaohongshu",
        tier_key="tier-2",
        share_link="https://example.com/post/1",
        payout_account="alice@example.com",
        payout_name="Alice",
        note="首发",
        status=PromoShareSubmissionStatus.SUBMITTED,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    resp = client.post(
        f"/api/v1/admin/promo/create-submissions/{row.id}/review",
        json={"status": "rejected", "review_note": "链接内容不完整"},
    )
    assert resp.status_code == 200
    db_session.refresh(row)
    assert row.status == PromoShareSubmissionStatus.REJECTED
    assert row.review_note == "链接内容不完整"

    approve = client.post(
        f"/api/v1/admin/promo/create-submissions/{row.id}/review",
        json={"status": "approved", "review_note": "改后通过", "reward_option_key": "tier-2"},
    )
    assert approve.status_code == 200
    db_session.refresh(row)
    db_session.refresh(user)
    assert row.status == PromoShareSubmissionStatus.APPROVED
    assert row.reward_credits == 10000
    assert user.credits == 10000
