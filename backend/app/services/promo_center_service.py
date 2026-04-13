from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import secrets

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    CreditType,
    Notification,
    Order,
    PromoBenefitRecord,
    PromoBenefitStatus,
    PromoBenefitType,
    PromoClassroom,
    PromoClassroomMember,
    PromoShareSubmission,
    PromoShareSubmissionStatus,
    ReferralRelation,
    User,
    UserInviteCode,
)
from app.services.credit_service import change_credits
from app.utils_qrcode import build_qrcode_data_url

SUBSIDY_SHARE_TASKS = [
    {"key": "wechat", "label": "分享朋友圈", "reward_credits": 5000, "note": "推荐检测体验并带上结果截图。"},
    {"key": "qq", "label": "分享QQ空间", "reward_credits": 3000, "note": "适合毕业群、班群和社团扩散。"},
    {"key": "weibo", "label": "分享微博", "reward_credits": 2000, "note": "建议带上平台关键词与使用感受。"},
]

SHARE_PLATFORM_PRESETS = {
    "weibo": {"label": "微博", "mark": "博", "max_reward": "得20元红包", "default_status": "ready"},
    "xiaohongshu": {"label": "小红书", "mark": "红", "max_reward": "得20元红包", "default_status": "ready"},
    "douyin": {"label": "抖音", "mark": "抖", "max_reward": "得20元红包", "default_status": "ready"},
    "zhihu": {"label": "知乎", "mark": "知", "max_reward": "得20元红包", "default_status": "ready"},
    "qq": {"label": "QQ", "mark": "Q", "max_reward": "得20元红包", "default_status": "ready"},
    "wechat": {"label": "微信", "mark": "微", "max_reward": "得20元红包", "default_status": "ready"},
}

SHARE_TIER_PRESETS = {
    "base": {"title": "5元红包", "reward_amount_cny": Decimal("5.00"), "reward_credits": 0, "coupon_name": None, "coupon_count": 0},
    "boost": {"title": "10元红包", "reward_amount_cny": Decimal("10.00"), "reward_credits": 0, "coupon_name": None, "coupon_count": 0},
    "top": {"title": "20元红包", "reward_amount_cny": Decimal("20.00"), "reward_credits": 0, "coupon_name": None, "coupon_count": 0},
}

CLASSROOM_LEVELS = [
    {"threshold": 40, "label": "钻石班"},
    {"threshold": 20, "label": "黄金班"},
    {"threshold": 10, "label": "白银班"},
    {"threshold": 0, "label": "青铜班"},
]


def _invite_code_for_user(user_id: int) -> str:
    return f"GW{int(user_id):06d}"


def _classroom_code() -> str:
    return f"CL{secrets.token_hex(3).upper()}"


def _format_cny(amount: Decimal | int | float | str | None) -> str:
    value = Decimal(str(amount or 0))
    return format(value, "f").rstrip("0").rstrip(".") or "0"


def _share_benefit_code(platform: str, tier_key: str) -> str:
    return f"{str(platform or '').strip().lower()}:{str(tier_key or '').strip().lower()}"


def ensure_user_invite_code(db: Session, user: User) -> UserInviteCode:
    row = db.query(UserInviteCode).filter(UserInviteCode.user_id == user.id).first()
    if row is not None:
        return row
    row = UserInviteCode(user_id=user.id, invite_code=_invite_code_for_user(user.id))
    db.add(row)
    db.flush()
    return row


def get_inviter_by_code(db: Session, invite_code: str) -> User | None:
    normalized = str(invite_code or "").strip().upper()
    if not normalized:
        return None
    row = db.query(UserInviteCode).filter(UserInviteCode.invite_code == normalized).first()
    if row is None:
        return None
    return db.get(User, row.user_id)


def _create_benefit_record(
    db: Session,
    *,
    user_id: int,
    scene: str,
    benefit_code: str,
    benefit_type: PromoBenefitType,
    title: str,
    credit_delta: int = 0,
    amount_cny: Decimal | int | float | str = Decimal("0"),
    coupon_name: str | None = None,
    coupon_count: int = 0,
    meta_json: dict | None = None,
) -> PromoBenefitRecord:
    row = PromoBenefitRecord(
        user_id=user_id,
        scene=scene,
        benefit_code=benefit_code,
        benefit_type=benefit_type,
        status=PromoBenefitStatus.GRANTED,
        title=title,
        credit_delta=int(credit_delta or 0),
        amount_cny=Decimal(str(amount_cny or 0)),
        coupon_name=coupon_name,
        coupon_count=int(coupon_count or 0),
        meta_json=meta_json,
        granted_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def grant_subsidy_share_claim(db: Session, *, user: User, task_key: str) -> tuple[PromoBenefitRecord, bool]:
    task = next((item for item in SUBSIDY_SHARE_TASKS if item["key"] == task_key), None)
    if task is None:
        raise ValueError("invalid_subsidy_task")

    existed = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == user.id,
            PromoBenefitRecord.scene == "subsidy_share",
            PromoBenefitRecord.benefit_code == task_key,
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .first()
    )
    if existed is not None:
        return existed, True

    reward_credits = int(task["reward_credits"])
    change_credits(
        db,
        user,
        tx_type=CreditType.SHARE_REWARD,
        delta=reward_credits,
        reason=f"积分补贴任务:{task_key}",
        related_id=f"promo_subsidy:{task_key}",
        source="promo_center",
    )
    db.add(Notification(user_id=user.id, title="积分补贴已到账", content=f"你已领取 {task['label']} 奖励 {reward_credits} 积分。"))
    record = _create_benefit_record(
        db,
        user_id=user.id,
        scene="subsidy_share",
        benefit_code=task_key,
        benefit_type=PromoBenefitType.CREDITS,
        title=task["label"],
        credit_delta=reward_credits,
    )
    return record, False


def grant_referral_login_benefit(db: Session, *, relation: ReferralRelation) -> None:
    benefit_code = f"login:{relation.id}"
    existed = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == relation.inviter_id,
            PromoBenefitRecord.scene == "invite_login",
            PromoBenefitRecord.benefit_code == benefit_code,
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .first()
    )
    if existed is not None:
        return

    inviter = db.query(User).filter(User.id == relation.inviter_id).with_for_update().first()
    if inviter is None:
        return

    change_credits(
        db,
        inviter,
        tx_type=CreditType.SHARE_REWARD,
        delta=2000,
        reason="邀请新用户登录奖励",
        related_id=f"promo_invite_login:{relation.id}",
        source=relation.source,
    )
    db.add(Notification(user_id=inviter.id, title="邀请登录奖励到账", content="有新用户通过你的专属链接完成登录，已发放 2000 积分。"))
    _create_benefit_record(
        db,
        user_id=inviter.id,
        scene="invite_login",
        benefit_code=benefit_code,
        benefit_type=PromoBenefitType.CREDITS,
        title="邀请新用户登录奖励",
        credit_delta=2000,
    )


def bind_promo_referral_relation(db: Session, *, invitee: User, referrer_code: str, source: str) -> ReferralRelation | None:
    inviter = get_inviter_by_code(db, referrer_code)
    if inviter is None or inviter.id == invitee.id:
        return None

    existed = db.query(ReferralRelation).filter(ReferralRelation.invitee_id == invitee.id).first()
    if existed is not None:
        return existed

    relation = ReferralRelation(
        inviter_id=inviter.id,
        invitee_id=invitee.id,
        invite_code=str(referrer_code).strip().upper(),
        source=source,
        status="registered",
    )
    db.add(relation)
    db.flush()
    grant_referral_login_benefit(db, relation=relation)
    return relation


def grant_first_order_promo_benefit(db: Session, *, order: Order) -> None:
    relation = (
        db.query(ReferralRelation)
        .filter(ReferralRelation.invitee_id == order.user_id)
        .with_for_update()
        .first()
    )
    if relation is None or relation.first_pay_reward_sent:
        return

    inviter = db.query(User).filter(User.id == relation.inviter_id).with_for_update().first()
    if inviter is None:
        return

    benefit_code = f"first_order:{relation.id}"
    existed = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == inviter.id,
            PromoBenefitRecord.scene == "invite_first_order",
            PromoBenefitRecord.benefit_code == benefit_code,
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .first()
    )
    if existed is not None:
        relation.first_pay_reward_sent = True
        relation.status = "first_paid"
        db.flush()
        return

    relation.first_pay_reward_sent = True
    relation.status = "first_paid"
    db.add(Notification(user_id=inviter.id, title="首单券包已到账", content="你邀请的用户已完成首单，系统已发放至尊查重券、AIGC 检测券和降重券。"))
    _create_benefit_record(
        db,
        user_id=inviter.id,
        scene="invite_first_order",
        benefit_code=benefit_code,
        benefit_type=PromoBenefitType.COUPON,
        title="首单券包奖励",
        coupon_name="至尊查重券 / AIGC 检测券 / 降重券",
        coupon_count=3,
        meta_json={
            "coupons": [
                {"name": "至尊查重券", "count": 1},
                {"name": "AIGC 检测券", "count": 1},
                {"name": "降重券", "count": 1},
            ]
        },
    )
    db.flush()


def _classroom_level(member_count: int) -> str:
    count = int(member_count or 0)
    for item in CLASSROOM_LEVELS:
        if count >= item["threshold"]:
            return item["label"]
    return "青铜班"


def _refresh_classroom_stats(db: Session, classroom: PromoClassroom) -> PromoClassroom:
    member_count = (
        db.query(func.count(PromoClassroomMember.id))
        .filter(PromoClassroomMember.classroom_id == classroom.id)
        .scalar()
        or 0
    )
    classroom.member_count = int(member_count)
    classroom.activity_score = min(99, 50 + int(member_count) * 2)
    classroom.level = _classroom_level(classroom.member_count)
    db.flush()
    return classroom


def create_classroom(db: Session, *, user: User, name: str) -> PromoClassroom:
    existed = (
        db.query(PromoClassroom)
        .filter(PromoClassroom.owner_user_id == user.id, PromoClassroom.status == "active")
        .first()
    )
    if existed is not None:
        return _refresh_classroom_stats(db, existed)

    classroom = PromoClassroom(
        owner_user_id=user.id,
        name=str(name or "").strip()[:120] or "格物毕业互助班",
        invite_code=_classroom_code(),
        member_count=1,
        activity_score=60,
        level="青铜班",
    )
    db.add(classroom)
    db.flush()
    db.add(PromoClassroomMember(classroom_id=classroom.id, user_id=user.id, role="owner"))
    db.flush()
    return classroom


def join_classroom(db: Session, *, user: User, invite_code: str) -> PromoClassroom:
    classroom = (
        db.query(PromoClassroom)
        .filter(PromoClassroom.invite_code == str(invite_code or "").strip().upper(), PromoClassroom.status == "active")
        .first()
    )
    if classroom is None:
        raise ValueError("classroom_not_found")

    existed = (
        db.query(PromoClassroomMember)
        .filter(PromoClassroomMember.classroom_id == classroom.id, PromoClassroomMember.user_id == user.id)
        .first()
    )
    if existed is None:
        db.add(PromoClassroomMember(classroom_id=classroom.id, user_id=user.id, role="member"))
        db.flush()
    return _refresh_classroom_stats(db, classroom)


def submit_share_review(
    db: Session,
    *,
    user: User,
    platform: str,
    tier_key: str,
    share_link: str,
    payout_account: str,
    payout_name: str,
    note: str,
) -> PromoShareSubmission:
    platform_key = str(platform or "").strip().lower()
    tier = SHARE_TIER_PRESETS.get(str(tier_key or "").strip().lower())
    if platform_key not in SHARE_PLATFORM_PRESETS:
        raise ValueError("invalid_platform")
    if tier is None:
        raise ValueError("invalid_tier")

    existed = (
        db.query(PromoShareSubmission)
        .filter(PromoShareSubmission.user_id == user.id, PromoShareSubmission.platform == platform_key)
        .first()
    )
    if existed is None:
        existed = PromoShareSubmission(
            user_id=user.id,
            platform=platform_key,
            tier_key=str(tier_key).strip().lower(),
            share_link=str(share_link or "").strip()[:500],
            payout_account=str(payout_account or "").strip()[:120],
            payout_name=str(payout_name or "").strip()[:120],
            note=str(note or "").strip()[:500],
            status=PromoShareSubmissionStatus.SUBMITTED,
            reward_credits=int(tier["reward_credits"]),
            reward_amount_cny=Decimal(str(tier["reward_amount_cny"])),
            coupon_name=tier["coupon_name"],
            coupon_count=int(tier["coupon_count"]),
        )
        db.add(existed)
    else:
        existed.tier_key = str(tier_key).strip().lower()
        existed.share_link = str(share_link or "").strip()[:500]
        existed.payout_account = str(payout_account or "").strip()[:120]
        existed.payout_name = str(payout_name or "").strip()[:120]
        existed.note = str(note or "").strip()[:500]
        existed.status = PromoShareSubmissionStatus.SUBMITTED
        existed.reward_credits = int(tier["reward_credits"])
        existed.reward_amount_cny = Decimal(str(tier["reward_amount_cny"]))
        existed.coupon_name = tier["coupon_name"]
        existed.coupon_count = int(tier["coupon_count"])
        existed.review_note = None
        existed.reviewed_by = None
        existed.reviewed_at = None
    db.flush()
    return existed


def review_share_submission(
    db: Session,
    *,
    submission: PromoShareSubmission,
    admin_id: int,
    approved: bool,
    review_note: str = "",
) -> tuple[PromoShareSubmission, bool]:
    if not approved:
        submission.status = PromoShareSubmissionStatus.REJECTED
        submission.review_note = review_note or "审核未通过，请调整内容后重新提交。"
        submission.reviewed_by = admin_id
        submission.reviewed_at = datetime.utcnow()
        db.flush()
        return submission, False

    benefit_code = _share_benefit_code(submission.platform, submission.tier_key)
    existed = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == submission.user_id,
            PromoBenefitRecord.scene == "share_center",
            PromoBenefitRecord.benefit_code == benefit_code,
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .first()
    )
    user = db.query(User).filter(User.id == submission.user_id).with_for_update().first()
    if user is None:
        raise ValueError("share_user_not_found")

    submission.status = PromoShareSubmissionStatus.APPROVED
    submission.review_note = review_note or ""
    submission.reviewed_by = admin_id
    submission.reviewed_at = datetime.utcnow()

    if existed is not None:
        existed.title = f"{SHARE_PLATFORM_PRESETS[submission.platform]['label']} 现金奖励"
        existed.amount_cny = Decimal(str(submission.reward_amount_cny or 0))
        existed.meta_json = {
            "submission_id": submission.id,
            "payout_account": submission.payout_account,
            "payout_name": submission.payout_name,
        }
        db.flush()
        return submission, True

    _create_benefit_record(
        db,
        user_id=user.id,
        scene="share_center",
        benefit_code=benefit_code,
        benefit_type=PromoBenefitType.CASH,
        title=f"{SHARE_PLATFORM_PRESETS[submission.platform]['label']} 现金奖励",
        credit_delta=0,
        amount_cny=submission.reward_amount_cny,
        coupon_name=submission.coupon_name,
        coupon_count=int(submission.coupon_count or 0),
        meta_json={
            "submission_id": submission.id,
            "payout_account": submission.payout_account,
            "payout_name": submission.payout_name,
        },
    )
    db.add(Notification(user_id=user.id, title="分享奖励审核通过", content=f"你提交的 {SHARE_PLATFORM_PRESETS[submission.platform]['label']} 分享任务已审核通过，等待人工发放红包。"))
    db.flush()
    return submission, False


def mark_share_reward_paid(
    db: Session,
    *,
    submission: PromoShareSubmission,
    admin_id: int,
    payout_note: str = "",
) -> tuple[PromoBenefitRecord, bool]:
    if submission.status != PromoShareSubmissionStatus.APPROVED:
        raise ValueError("share_submission_not_approved")

    benefit = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == submission.user_id,
            PromoBenefitRecord.scene == "share_center",
            PromoBenefitRecord.benefit_code == _share_benefit_code(submission.platform, submission.tier_key),
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .with_for_update()
        .first()
    )
    if benefit is None:
        raise ValueError("share_benefit_not_found")
    if benefit.payout_status == "paid":
        return benefit, True

    meta_json = dict(benefit.meta_json) if isinstance(benefit.meta_json, dict) else {}
    if payout_note:
        meta_json["payout_note"] = payout_note
    benefit.meta_json = meta_json or None
    benefit.payout_status = "paid"
    benefit.paid_by = admin_id
    benefit.paid_at = datetime.utcnow()
    db.add(
        Notification(
            user_id=submission.user_id,
            title="分享红包已发放",
            content=f"你提交的 {SHARE_PLATFORM_PRESETS[submission.platform]['label']} 分享红包已人工发放，请前往账户余额查看。",
        )
    )
    db.flush()
    return benefit, False


def build_promo_center_payload(db: Session, *, user: User, frontend_base_url: str) -> dict:
    invite_code = ensure_user_invite_code(db, user)
    invite_link = f"{frontend_base_url.rstrip('/')}/register?ref={invite_code.invite_code}"

    share_claim_codes = {
        row.benefit_code
        for row in db.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == user.id, PromoBenefitRecord.scene == "subsidy_share", PromoBenefitRecord.status == PromoBenefitStatus.GRANTED)
        .all()
    }
    subsidy_tasks = [
        {
            **task,
            "status": "claimed" if task["key"] in share_claim_codes else "ready",
        }
        for task in SUBSIDY_SHARE_TASKS
    ]

    relations = (
        db.query(ReferralRelation)
        .filter(ReferralRelation.inviter_id == user.id)
        .order_by(desc(ReferralRelation.created_at))
        .all()
    )
    invite_login_count = len(relations)
    first_order_count = sum(1 for row in relations if row.status == "first_paid" or row.first_pay_reward_sent)

    owned_classroom = (
        db.query(PromoClassroom)
        .filter(PromoClassroom.owner_user_id == user.id, PromoClassroom.status == "active")
        .first()
    )
    if owned_classroom is not None:
        owned_classroom = _refresh_classroom_stats(db, owned_classroom)

    leaderboard = (
        db.query(PromoClassroom)
        .filter(PromoClassroom.status == "active")
        .order_by(desc(PromoClassroom.activity_score), desc(PromoClassroom.member_count), desc(PromoClassroom.created_at))
        .limit(10)
        .all()
    )

    share_rows = (
        db.query(PromoShareSubmission)
        .filter(PromoShareSubmission.user_id == user.id)
        .order_by(desc(PromoShareSubmission.created_at))
        .all()
    )
    share_map = {row.platform: row for row in share_rows}
    share_benefit_map = {
        row.benefit_code: row
        for row in db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == user.id,
            PromoBenefitRecord.scene == "share_center",
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
        )
        .all()
    }
    share_platforms = []
    for key, preset in SHARE_PLATFORM_PRESETS.items():
        row = share_map.get(key)
        share_platforms.append(
            {
                "key": key,
                "label": preset["label"],
                "mark": preset["mark"],
                "reward": preset["max_reward"],
                "status": (row.status.value if row is not None else preset["default_status"]),
            }
        )

    share_records = [
        {
            "id": row.id,
            "platform": SHARE_PLATFORM_PRESETS.get(row.platform, {}).get("label", row.platform),
            "note": (
                "已提交审核，等待后台人工审核"
                if row.status == PromoShareSubmissionStatus.SUBMITTED
                else (
                    row.review_note or "审核未通过，请按要求调整后重新提交"
                    if row.status == PromoShareSubmissionStatus.REJECTED
                    else (
                        "审核通过，红包已人工发放"
                        if share_benefit_map.get(_share_benefit_code(row.platform, row.tier_key), None) is not None
                        and share_benefit_map[_share_benefit_code(row.platform, row.tier_key)].payout_status == "paid"
                        else "审核通过，等待人工发放红包"
                    )
                )
            ),
            "status": row.status.value,
            "payout_status": (
                share_benefit_map[_share_benefit_code(row.platform, row.tier_key)].payout_status
                if share_benefit_map.get(_share_benefit_code(row.platform, row.tier_key)) is not None
                else "none"
            ),
            "reward": f"{_format_cny(row.reward_amount_cny)}元红包",
        }
        for row in share_rows[:10]
    ]

    benefit_rows = (
        db.query(PromoBenefitRecord)
        .filter(PromoBenefitRecord.user_id == user.id)
        .order_by(desc(PromoBenefitRecord.created_at))
        .limit(20)
        .all()
    )
    subsidy_ledger = []
    for row in benefit_rows:
        amount_text = f"{_format_cny(row.amount_cny)}元红包" if Decimal(str(row.amount_cny or 0)) > 0 else None
        coupon_text = f"{row.coupon_name} x{row.coupon_count}" if row.coupon_name else "-"
        if row.benefit_type == PromoBenefitType.CASH and amount_text:
            status_text = "已打款" if row.payout_status == "paid" else "待打款"
            status_value = "done" if row.payout_status == "paid" else "current"
            note_text = "红包已人工发放，请前往账户余额查看。" if row.payout_status == "paid" else "审核已通过，等待运营人工发放红包。"
        else:
            status_text = "已发放" if row.status == PromoBenefitStatus.GRANTED else "已撤回"
            status_value = "done" if row.status == PromoBenefitStatus.GRANTED else "revoked"
            note_text = row.meta_json.get("note") if isinstance(row.meta_json, dict) and row.meta_json.get("note") else "活动奖励已入账"
        subsidy_ledger.append(
            {
                "title": row.title,
                "note": note_text,
                "status": status_value,
                "statusText": status_text,
                "reward": amount_text if amount_text else (f"+{row.credit_delta} 积分" if int(row.credit_delta or 0) > 0 else coupon_text),
            }
        )

    if not subsidy_ledger:
        subsidy_ledger = [
            {
                "title": "奖励记录待产生",
                "note": "完成分享、邀请登录和首单任务后，奖励会自动出现在这里。",
                "status": "current",
                "statusText": "未开始",
                "reward": "-",
            }
        ]

    return {
        "invite": {
            "invite_code": invite_code.invite_code,
            "invite_link": invite_link,
            "qrcode_data_url": build_qrcode_data_url(invite_link),
        },
        "subsidy": {
            "share_tasks": subsidy_tasks,
            "invite_login_count": invite_login_count,
            "first_order_count": first_order_count,
            "ledger": subsidy_ledger,
        },
        "classroom": {
            "owned": (
                {
                    "id": owned_classroom.id,
                    "name": owned_classroom.name,
                    "invite_code": owned_classroom.invite_code,
                    "level": owned_classroom.level,
                    "member_count": owned_classroom.member_count,
                    "activity_score": owned_classroom.activity_score,
                }
                if owned_classroom is not None
                else None
            ),
            "leaderboard": [
                {
                    "rank": index + 1,
                    "name": row.name,
                    "members": row.member_count,
                    "activity": row.activity_score,
                    "level": row.level,
                }
                for index, row in enumerate(leaderboard)
            ],
        },
        "share_center": {
            "platforms": share_platforms,
            "records": share_records,
        },
    }


def build_admin_promo_overview(db: Session) -> dict:
    classroom_count = db.query(func.count(PromoClassroom.id)).filter(PromoClassroom.status == "active").scalar() or 0
    share_submission_count = db.query(func.count(PromoShareSubmission.id)).scalar() or 0
    pending_share_count = db.query(func.count(PromoShareSubmission.id)).filter(PromoShareSubmission.status == PromoShareSubmissionStatus.SUBMITTED).scalar() or 0
    pending_payout_count = (
        db.query(func.count(PromoBenefitRecord.id))
        .filter(
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
            PromoBenefitRecord.benefit_type == PromoBenefitType.CASH,
            PromoBenefitRecord.payout_status == "pending",
        )
        .scalar()
        or 0
    )
    pending_payout_amount = (
        db.query(func.coalesce(func.sum(PromoBenefitRecord.amount_cny), 0))
        .filter(
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
            PromoBenefitRecord.benefit_type == PromoBenefitType.CASH,
            PromoBenefitRecord.payout_status == "pending",
        )
        .scalar()
        or 0
    )
    paid_cash_total = (
        db.query(func.coalesce(func.sum(PromoBenefitRecord.amount_cny), 0))
        .filter(
            PromoBenefitRecord.status == PromoBenefitStatus.GRANTED,
            PromoBenefitRecord.benefit_type == PromoBenefitType.CASH,
            PromoBenefitRecord.payout_status == "paid",
        )
        .scalar()
        or 0
    )
    return {
        "classroom_count": int(classroom_count),
        "share_submission_count": int(share_submission_count),
        "pending_share_count": int(pending_share_count),
        "pending_payout_count": int(pending_payout_count),
        "pending_payout_amount": float(pending_payout_amount),
        "approved_cash_total": float(pending_payout_amount),
        "paid_cash_total": float(paid_cash_total),
    }
