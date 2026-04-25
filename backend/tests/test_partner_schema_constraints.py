import pytest
from sqlalchemy.exc import IntegrityError

from app.models import PartnerChannel, PartnerPolicy


def test_partner_channel_level_check_constraint(db_session) -> None:
    row = PartnerChannel(
        channel_code="CHBADL01",
        name="非法层级渠道",
        contact_name="测试",
        contact_phone="13800139001",
        status="active",
        order_token="order-token-bad-level",
        portal_token="portal-token-bad-level",
        level=4,
        default_rebate_rate_bp=1000,
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_partner_policy_rate_check_constraint(db_session) -> None:
    channel = PartnerChannel(
        channel_code="CHGOOD01",
        name="合法渠道",
        contact_name="测试",
        contact_phone="13800139002",
        status="active",
        order_token="order-token-good",
        portal_token="portal-token-good",
        level=1,
        default_rebate_rate_bp=1000,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)

    bad_policy = PartnerPolicy(
        channel_id=channel.id,
        package_name="超限包",
        rebate_rate_bp=12000,
        is_active=True,
    )
    db_session.add(bad_policy)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
