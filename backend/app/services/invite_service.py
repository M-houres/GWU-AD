from __future__ import annotations

import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import BizError
from app.models import (
    CreditType,
    PartnerUserBinding,
    PromoBenefitRecord,
    PromoBenefitStatus,
    PromoBenefitType,
    ReferralRelation,
    SystemConfig,
    User,
    UserInviteCode,
)
from app.services.credit_service import change_credits
from app.services.partner_rebate_service import bind_partner_channel, get_bound_channel_payload


def _read_promo_center_reward_rules(db: Session) -> dict:
    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.category == "system", SystemConfig.config_key == "promo_center")
        .first()
    )
    raw = row.config_value if row and isinstance(row.config_value, dict) else {}
    invite_raw = raw.get("reward_rules", {}).get("invite", {}) if isinstance(raw.get("reward_rules"), dict) else {}

    def _safe_int(value: object, default: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = int(default)
        return max(0, min(parsed, 1_000_000))

    legacy_inviter_reward = _safe_int(raw.get("invite_reward_points"), 2000) // 2 if isinstance(raw, dict) else 1000
    return {
        "invitee_bind_reward_points": _safe_int(invite_raw.get("invitee_bind_reward_points"), 2000),
        "inviter_valid_invite_reward_points": _safe_int(
            invite_raw.get("inviter_valid_invite_reward_points"),
            legacy_inviter_reward or 1000,
        ),
        "milestones": invite_raw.get("milestones") if isinstance(invite_raw.get("milestones"), list) else [
            {"threshold": 5, "reward_points": 3000, "label": "邀请满 5 人"},
            {"threshold": 20, "reward_points": 10000, "label": "邀请满 20 人"},
            {"threshold": 50, "reward_points": 30000, "label": "邀请满 50 人"},
        ],
    }


def ensure_user_invite_code(db: Session, *, user_id: int) -> UserInviteCode:
    row = db.query(UserInviteCode).filter(UserInviteCode.user_id == user_id).with_for_update().first()
    if row is not None:
        return row
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(30):
        candidate = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = db.query(UserInviteCode.user_id).filter(UserInviteCode.invite_code == candidate).first()
        if exists:
            continue
        row = UserInviteCode(user_id=user_id, invite_code=candidate)
        db.add(row)
        db.flush()
        return row
    raise BizError(code=4401, message="邀请码生成失败，请稍后重试")


def _invite_benefit_code(*parts: object) -> str:
    return ":".join(str(part).strip() for part in parts if str(part).strip())[:64]


def _grant_invite_credit_reward(
    db: Session,
    *,
    user: User,
    scene: str,
    benefit_code: str,
    reward_points: int,
    title: str,
    meta: dict | None = None,
) -> PromoBenefitRecord:
    row = (
        db.query(PromoBenefitRecord)
        .filter(
            PromoBenefitRecord.user_id == user.id,
            PromoBenefitRecord.scene == scene,
            PromoBenefitRecord.benefit_code == benefit_code,
        )
        .with_for_update()
        .first()
    )
    if row is not None:
        return row
    points = max(0, int(reward_points or 0))
    if points > 0:
        change_credits(
            db,
            user,
            tx_type=CreditType.SHARE_REWARD,
            delta=points,
            reason=title,
            related_id=f"promo_reward:{scene}:{benefit_code}",
            source="promo_center",
        )
    row = PromoBenefitRecord(
        user_id=int(user.id),
        scene=scene,
        benefit_code=benefit_code,
        benefit_type=PromoBenefitType.CREDITS,
        status=PromoBenefitStatus.GRANTED,
        title=title[:120],
        credit_delta=points,
        payout_status="paid" if points > 0 else "pending",
        meta_json=meta or {},
    )
    db.add(row)
    db.flush()
    return row


def _inherit_inviter_channel(db: Session, *, inviter_id: int, invitee_id: int) -> None:
    invitee_binding = db.query(PartnerUserBinding.user_id).filter(PartnerUserBinding.user_id == invitee_id).first()
    if invitee_binding is not None:
        return
    inviter_payload = get_bound_channel_payload(db, user_id=inviter_id)
    if not inviter_payload or not inviter_payload.get("active"):
        return
    bind_partner_channel(
        db,
        user_id=invitee_id,
        channel_id=int(inviter_payload["channel_id"]),
        bind_source="invite",
        force_rebind=False,
    )


def grant_invite_rewards(
    db: Session,
    *,
    relation: ReferralRelation,
    invitee: User,
) -> None:
    inviter = db.get(User, int(relation.inviter_id))
    if inviter is None:
        raise BizError(code=4406, message="邀请人不存在，无法发放奖励")

    reward_rules = _read_promo_center_reward_rules(db)
    invitee_points = max(0, int(reward_rules.get("invitee_bind_reward_points") or 0))
    inviter_points = max(0, int(reward_rules.get("inviter_valid_invite_reward_points") or 0))
    scene = "invite"

    _grant_invite_credit_reward(
        db,
        user=invitee,
        scene=scene,
        benefit_code=_invite_benefit_code("relation", relation.id, "invitee-bind"),
        reward_points=invitee_points,
        title="邀请绑定奖励",
        meta={
            "relation_id": int(relation.id),
            "role": "invitee",
            "inviter_user_id": int(inviter.id),
        },
    )
    _grant_invite_credit_reward(
        db,
        user=inviter,
        scene=scene,
        benefit_code=_invite_benefit_code("relation", relation.id, "inviter-valid"),
        reward_points=inviter_points,
        title="有效邀请奖励",
        meta={
            "relation_id": int(relation.id),
            "role": "inviter",
            "invitee_user_id": int(invitee.id),
        },
    )

    relation.register_reward_sent = True
    _inherit_inviter_channel(db, inviter_id=int(inviter.id), invitee_id=int(invitee.id))
    db.flush()

    valid_invite_count = (
        db.query(func.count(ReferralRelation.id))
        .filter(
            ReferralRelation.inviter_id == inviter.id,
            ReferralRelation.register_reward_sent.is_(True),
        )
        .scalar()
        or 0
    )
    milestone_rules = reward_rules.get("milestones") if isinstance(reward_rules.get("milestones"), list) else []
    for item in milestone_rules:
        threshold = max(0, int(item.get("threshold") or 0))
        reward_points = max(0, int(item.get("reward_points") or 0))
        if threshold <= 0 or reward_points <= 0 or int(valid_invite_count) < threshold:
            continue
        label = str(item.get("label") or "").strip()[:48] or f"邀请满 {threshold} 人"
        _grant_invite_credit_reward(
            db,
            user=inviter,
            scene=scene,
            benefit_code=_invite_benefit_code("milestone", inviter.id, threshold),
            reward_points=reward_points,
            title=label,
            meta={
                "role": "inviter",
                "threshold": threshold,
                "valid_invite_count": int(valid_invite_count),
            },
        )


def bind_invite_code_for_user(
    db: Session,
    *,
    user: User,
    invite_code: str,
    source: str = "web",
    strict: bool = True,
) -> ReferralRelation | None:
    normalized_code = str(invite_code or "").strip().upper()
    if not normalized_code:
        if strict:
            raise BizError(code=4402, message="请输入邀请码")
        return None

    own_code = ensure_user_invite_code(db, user_id=int(user.id))
    if normalized_code == own_code.invite_code:
        if strict:
            raise BizError(code=4403, message="不能绑定自己的邀请码")
        return None

    existing = db.query(ReferralRelation).filter(ReferralRelation.invitee_id == user.id).first()
    if existing is not None:
        if strict:
            raise BizError(code=4404, message="当前账号已绑定邀请码")
        return existing

    inviter_code = db.query(UserInviteCode).filter(UserInviteCode.invite_code == normalized_code).first()
    if inviter_code is None:
        if strict:
            raise BizError(code=4405, message="邀请码不存在")
        return None
    if int(inviter_code.user_id) == int(user.id):
        if strict:
            raise BizError(code=4403, message="不能绑定自己的邀请码")
        return None

    relation = ReferralRelation(
        inviter_id=int(inviter_code.user_id),
        invitee_id=int(user.id),
        invite_code=normalized_code,
        source=str(source or "web")[:20] or "web",
        status="registered",
    )
    db.add(relation)
    db.flush()
    grant_invite_rewards(db, relation=relation, invitee=user)
    return relation
