from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    CreditTransaction,
    Notification,
    Order,
    PartnerOrderAttribution,
    PartnerRebateLedger,
    PartnerUserBinding,
    PromoBenefitRecord,
    PromoClassroomMember,
    PromoShareSubmission,
    ReferralRelation,
    ReferralReward,
    Task,
    User,
    UserInviteCode,
    UserShareTaskSubmission,
)


def _is_virtual_miniprogram_phone(phone: str | None) -> bool:
    raw = str(phone or "").strip()
    return len(raw) == 11 and raw.startswith("19")


def merge_user_into(
    db: Session,
    *,
    from_user: User,
    to_user: User,
) -> User:
    if int(from_user.id) == int(to_user.id):
        return to_user

    from_id = int(from_user.id)
    to_id = int(to_user.id)

    db.query(Order).filter(Order.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(Task).filter(Task.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(Notification).filter(Notification.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(PartnerOrderAttribution).filter(PartnerOrderAttribution.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(PartnerRebateLedger).filter(PartnerRebateLedger.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(ReferralReward).filter(ReferralReward.inviter_id == from_id).update({"inviter_id": to_id}, synchronize_session=False)
    db.query(ReferralReward).filter(ReferralReward.invitee_id == from_id).update({"invitee_id": to_id}, synchronize_session=False)

    if db.query(UserInviteCode.user_id).filter(UserInviteCode.user_id == to_id).first() is None:
        db.query(UserInviteCode).filter(UserInviteCode.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    else:
        db.query(UserInviteCode).filter(UserInviteCode.user_id == from_id).delete(synchronize_session=False)

    to_binding = db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == to_id).first()
    if to_binding is None:
        db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    else:
        db.query(PartnerUserBinding).filter(PartnerUserBinding.user_id == from_id).delete(synchronize_session=False)

    to_invitee_relation = db.query(ReferralRelation).filter(ReferralRelation.invitee_id == to_id).first()
    if to_invitee_relation is None:
        db.query(ReferralRelation).filter(ReferralRelation.invitee_id == from_id).update({"invitee_id": to_id}, synchronize_session=False)
    else:
        db.query(ReferralRelation).filter(ReferralRelation.invitee_id == from_id).delete(synchronize_session=False)
    db.query(ReferralRelation).filter(ReferralRelation.inviter_id == from_id).update({"inviter_id": to_id}, synchronize_session=False)

    if not db.query(UserShareTaskSubmission.id).filter(UserShareTaskSubmission.user_id == to_id).first():
        db.query(UserShareTaskSubmission).filter(UserShareTaskSubmission.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    else:
        db.query(UserShareTaskSubmission).filter(UserShareTaskSubmission.user_id == from_id).delete(synchronize_session=False)

    if not db.query(PromoShareSubmission.id).filter(PromoShareSubmission.user_id == to_id).first():
        db.query(PromoShareSubmission).filter(PromoShareSubmission.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    else:
        db.query(PromoShareSubmission).filter(PromoShareSubmission.user_id == from_id).delete(synchronize_session=False)

    db.query(PromoBenefitRecord).filter(PromoBenefitRecord.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(PromoClassroomMember).filter(PromoClassroomMember.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)
    db.query(CreditTransaction).filter(CreditTransaction.user_id == from_id).update({"user_id": to_id}, synchronize_session=False)

    to_user.credits = max(int(to_user.credits or 0), int(from_user.credits or 0))
    if from_user.wechat_openid_mp and not to_user.wechat_openid_mp:
        to_user.wechat_openid_mp = from_user.wechat_openid_mp
    if from_user.wechat_unionid and not to_user.wechat_unionid:
        to_user.wechat_unionid = from_user.wechat_unionid
    if from_user.wechat_openid_web and not to_user.wechat_openid_web:
        to_user.wechat_openid_web = from_user.wechat_openid_web
    if from_user.openid and not to_user.openid:
        to_user.openid = from_user.openid
    if not to_user.nickname and from_user.nickname:
        to_user.nickname = from_user.nickname
    if not to_user.source and from_user.source:
        to_user.source = from_user.source

    from_user.phone = f"del{from_id:09d}"
    from_user.nickname = "已合并旧账号"
    from_user.openid = None
    from_user.wechat_unionid = None
    from_user.wechat_openid_web = None
    from_user.wechat_openid_mp = None
    from_user.is_banned = True
    from_user.credits = 0
    db.flush()
    return to_user


def merge_miniprogram_legacy_user_if_needed(
    db: Session,
    *,
    openid_user: User | None,
    phone_user: User | None,
) -> tuple[User | None, bool]:
    if openid_user is None or phone_user is None:
        return openid_user or phone_user, False
    if int(openid_user.id) == int(phone_user.id):
        return phone_user, False
    if not _is_virtual_miniprogram_phone(openid_user.phone):
        return None, False
    merged_user = merge_user_into(db, from_user=openid_user, to_user=phone_user)
    return merged_user, True
