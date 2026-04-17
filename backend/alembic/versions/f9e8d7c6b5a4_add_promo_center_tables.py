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
PROMO_BENEFIT_TABLE = "promo_benefit_records"
PROMO_CLASSROOM_TABLE = "promo_classrooms"
PROMO_CLASSROOM_MEMBER_TABLE = "promo_classroom_members"
PROMO_SHARE_TABLE = "promo_share_submissions"

PROMO_BENEFIT_INDEXES = (
    ("ix_promo_benefit_records_user_id", ["user_id"]),
    ("ix_promo_benefit_records_scene", ["scene"]),
    ("ix_promo_benefit_records_benefit_type", ["benefit_type"]),
    ("ix_promo_benefit_records_status", ["status"]),
    ("ix_promo_benefit_records_payout_status", ["payout_status"]),
    ("ix_promo_benefit_records_paid_by", ["paid_by"]),
)
PROMO_CLASSROOM_INDEXES = (
    ("ix_promo_classrooms_owner_user_id", ["owner_user_id"]),
    ("ix_promo_classrooms_status", ["status"]),
    ("ix_promo_classrooms_member_count", ["member_count"]),
)
PROMO_CLASSROOM_MEMBER_INDEXES = (
    ("ix_promo_classroom_members_classroom_id", ["classroom_id"]),
    ("ix_promo_classroom_members_user_id", ["user_id"]),
)
PROMO_SHARE_INDEXES = (
    ("ix_promo_share_submissions_user_id", ["user_id"]),
    ("ix_promo_share_submissions_platform", ["platform"]),
    ("ix_promo_share_submissions_status", ["status"]),
    ("ix_promo_share_submissions_reviewed_by", ["reviewed_by"]),
)


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _existing_index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    try:
        return {str(item.get("name")) for item in inspector.get_indexes(table_name) if item.get("name")}
    except Exception:
        return set()


def _create_missing_indexes(bind, table_name: str, indexes: tuple[tuple[str, list[str]], ...]) -> None:
    existing = _existing_index_names(bind, table_name)
    for index_name, columns in indexes:
        if index_name in existing:
            continue
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, PROMO_BENEFIT_TABLE):
        op.create_table(
            PROMO_BENEFIT_TABLE,
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
    _create_missing_indexes(bind, PROMO_BENEFIT_TABLE, PROMO_BENEFIT_INDEXES)

    if not _table_exists(bind, PROMO_CLASSROOM_TABLE):
        op.create_table(
            PROMO_CLASSROOM_TABLE,
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
    _create_missing_indexes(bind, PROMO_CLASSROOM_TABLE, PROMO_CLASSROOM_INDEXES)

    if not _table_exists(bind, PROMO_CLASSROOM_MEMBER_TABLE):
        op.create_table(
            PROMO_CLASSROOM_MEMBER_TABLE,
            sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
            sa.Column("classroom_id", id_pk_type, sa.ForeignKey("promo_classrooms.id"), nullable=False),
            sa.Column("user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False, server_default="member"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("classroom_id", "user_id", name="uk_promo_classroom_member"),
        )
    _create_missing_indexes(bind, PROMO_CLASSROOM_MEMBER_TABLE, PROMO_CLASSROOM_MEMBER_INDEXES)

    if not _table_exists(bind, PROMO_SHARE_TABLE):
        op.create_table(
            PROMO_SHARE_TABLE,
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
    _create_missing_indexes(bind, PROMO_SHARE_TABLE, PROMO_SHARE_INDEXES)


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, PROMO_SHARE_TABLE):
        existing_indexes = _existing_index_names(bind, PROMO_SHARE_TABLE)
        for index_name, _columns in reversed(PROMO_SHARE_INDEXES):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=PROMO_SHARE_TABLE)
        op.drop_table(PROMO_SHARE_TABLE)

    if _table_exists(bind, PROMO_CLASSROOM_MEMBER_TABLE):
        existing_indexes = _existing_index_names(bind, PROMO_CLASSROOM_MEMBER_TABLE)
        for index_name, _columns in reversed(PROMO_CLASSROOM_MEMBER_INDEXES):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=PROMO_CLASSROOM_MEMBER_TABLE)
        op.drop_table(PROMO_CLASSROOM_MEMBER_TABLE)

    if _table_exists(bind, PROMO_CLASSROOM_TABLE):
        existing_indexes = _existing_index_names(bind, PROMO_CLASSROOM_TABLE)
        for index_name, _columns in reversed(PROMO_CLASSROOM_INDEXES):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=PROMO_CLASSROOM_TABLE)
        op.drop_table(PROMO_CLASSROOM_TABLE)

    if _table_exists(bind, PROMO_BENEFIT_TABLE):
        existing_indexes = _existing_index_names(bind, PROMO_BENEFIT_TABLE)
        for index_name, _columns in reversed(PROMO_BENEFIT_INDEXES):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=PROMO_BENEFIT_TABLE)
        op.drop_table(PROMO_BENEFIT_TABLE)
