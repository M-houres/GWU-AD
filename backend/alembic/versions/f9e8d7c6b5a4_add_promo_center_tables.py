"""add promo center tables

Revision ID: f9e8d7c6b5a4
Revises: a7c4d2e9f1b0
Create Date: 2026-04-13 20:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f9e8d7c6b5a4"
down_revision = "a7c4d2e9f1b0"
branch_labels = None
depends_on = None

id_pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "promo_benefit_records",
        sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scene", sa.String(length=32), nullable=False),
        sa.Column("benefit_code", sa.String(length=64), nullable=False),
        sa.Column("benefit_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="granted"),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("credit_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_cny", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("coupon_name", sa.String(length=120), nullable=True),
        sa.Column("coupon_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payout_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("paid_by", id_pk_type, sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "scene", "benefit_code", name="uk_promo_benefit_user_scene_code"),
    )
    op.create_index("ix_promo_benefit_records_user_id", "promo_benefit_records", ["user_id"])
    op.create_index("ix_promo_benefit_records_scene", "promo_benefit_records", ["scene"])
    op.create_index("ix_promo_benefit_records_benefit_type", "promo_benefit_records", ["benefit_type"])
    op.create_index("ix_promo_benefit_records_status", "promo_benefit_records", ["status"])
    op.create_index("ix_promo_benefit_records_payout_status", "promo_benefit_records", ["payout_status"])
    op.create_index("ix_promo_benefit_records_paid_by", "promo_benefit_records", ["paid_by"])

    op.create_table(
        "promo_classrooms",
        sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("invite_code", sa.String(length=24), nullable=False),
        sa.Column("level", sa.String(length=24), nullable=False, server_default="青铜班"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("activity_score", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("invite_code", name="uq_promo_classrooms_invite_code"),
    )
    op.create_index("ix_promo_classrooms_owner_user_id", "promo_classrooms", ["owner_user_id"])
    op.create_index("ix_promo_classrooms_status", "promo_classrooms", ["status"])
    op.create_index("ix_promo_classrooms_member_count", "promo_classrooms", ["member_count"])

    op.create_table(
        "promo_classroom_members",
        sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
        sa.Column("classroom_id", id_pk_type, sa.ForeignKey("promo_classrooms.id"), nullable=False),
        sa.Column("user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("classroom_id", "user_id", name="uk_promo_classroom_member"),
    )
    op.create_index("ix_promo_classroom_members_classroom_id", "promo_classroom_members", ["classroom_id"])
    op.create_index("ix_promo_classroom_members_user_id", "promo_classroom_members", ["user_id"])

    op.create_table(
        "promo_share_submissions",
        sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("tier_key", sa.String(length=24), nullable=False),
        sa.Column("share_link", sa.String(length=500), nullable=False),
        sa.Column("payout_account", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("payout_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("note", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("reward_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_amount_cny", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("coupon_name", sa.String(length=120), nullable=True),
        sa.Column("coupon_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_note", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by", id_pk_type, sa.ForeignKey("admin_users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "platform", name="uk_promo_share_user_platform"),
    )
    op.create_index("ix_promo_share_submissions_user_id", "promo_share_submissions", ["user_id"])
    op.create_index("ix_promo_share_submissions_platform", "promo_share_submissions", ["platform"])
    op.create_index("ix_promo_share_submissions_status", "promo_share_submissions", ["status"])
    op.create_index("ix_promo_share_submissions_reviewed_by", "promo_share_submissions", ["reviewed_by"])


def downgrade() -> None:
    op.drop_index("ix_promo_share_submissions_reviewed_by", table_name="promo_share_submissions")
    op.drop_index("ix_promo_share_submissions_status", table_name="promo_share_submissions")
    op.drop_index("ix_promo_share_submissions_platform", table_name="promo_share_submissions")
    op.drop_index("ix_promo_share_submissions_user_id", table_name="promo_share_submissions")
    op.drop_table("promo_share_submissions")

    op.drop_index("ix_promo_classroom_members_user_id", table_name="promo_classroom_members")
    op.drop_index("ix_promo_classroom_members_classroom_id", table_name="promo_classroom_members")
    op.drop_table("promo_classroom_members")

    op.drop_index("ix_promo_classrooms_member_count", table_name="promo_classrooms")
    op.drop_index("ix_promo_classrooms_status", table_name="promo_classrooms")
    op.drop_index("ix_promo_classrooms_owner_user_id", table_name="promo_classrooms")
    op.drop_table("promo_classrooms")

    op.drop_index("ix_promo_benefit_records_status", table_name="promo_benefit_records")
    op.drop_index("ix_promo_benefit_records_benefit_type", table_name="promo_benefit_records")
    op.drop_index("ix_promo_benefit_records_scene", table_name="promo_benefit_records")
    op.drop_index("ix_promo_benefit_records_user_id", table_name="promo_benefit_records")
    op.drop_index("ix_promo_benefit_records_paid_by", table_name="promo_benefit_records")
    op.drop_index("ix_promo_benefit_records_payout_status", table_name="promo_benefit_records")
    op.drop_table("promo_benefit_records")
