"""add share task submissions and share reward

Revision ID: a7c4d2e9f1b0
Revises: f1a2b3c4d5e6
Create Date: 2026-04-13 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a7c4d2e9f1b0"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


OLD_CREDIT_TYPE_VALUES = (
    "INIT",
    "TASK_CONSUME",
    "TASK_REFUND",
    "PACKAGE_PAY",
    "REFERRAL_INVITE",
    "REFERRAL_BONUS",
    "REFERRAL_FIRST_PAY",
    "REFERRAL_RECURRING",
    "ADMIN_ADJUST",
)
NEW_CREDIT_TYPE_VALUES = OLD_CREDIT_TYPE_VALUES + ("SHARE_REWARD",)

old_credit_type_enum = sa.Enum(*OLD_CREDIT_TYPE_VALUES, name="credittype")
new_credit_type_enum = sa.Enum(*NEW_CREDIT_TYPE_VALUES, name="credittype")
share_task_status_enum = sa.Enum("TODO", "PENDING", "APPROVED", "REJECTED", name="sharetaskstatus")
id_pk_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
SHARE_TASK_TABLE = "user_share_task_submissions"
SHARE_TASK_INDEXES = (
    ("ix_user_share_task_submissions_user_id", ["user_id"]),
    ("ix_user_share_task_submissions_platform", ["platform"]),
    ("ix_user_share_task_submissions_status", ["status"]),
    ("ix_user_share_task_submissions_reviewed_by", ["reviewed_by"]),
)


def _upgrade_postgresql_enum() -> None:
    op.execute("ALTER TYPE credittype ADD VALUE IF NOT EXISTS 'SHARE_REWARD'")


def _upgrade_mysql_enum() -> None:
    op.alter_column(
        "credit_transactions",
        "tx_type",
        existing_type=old_credit_type_enum,
        type_=new_credit_type_enum,
        existing_nullable=False,
    )


def _downgrade_postgresql_enum(bind) -> None:
    op.execute("DELETE FROM credit_transactions WHERE tx_type = 'SHARE_REWARD'")
    op.execute("ALTER TYPE credittype RENAME TO credittype_old")
    old_credit_type_enum.create(bind, checkfirst=False)
    op.execute(
        """
        ALTER TABLE credit_transactions
        ALTER COLUMN tx_type TYPE credittype
        USING (
            CASE
                WHEN tx_type::text = 'SHARE_REWARD' THEN 'ADMIN_ADJUST'
                ELSE tx_type::text
            END
        )::credittype
        """
    )
    op.execute("DROP TYPE credittype_old")


def _downgrade_mysql_enum() -> None:
    op.execute("DELETE FROM credit_transactions WHERE tx_type = 'SHARE_REWARD'")
    op.alter_column(
        "credit_transactions",
        "tx_type",
        existing_type=new_credit_type_enum,
        type_=old_credit_type_enum,
        existing_nullable=False,
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


def _create_missing_indexes(bind, table_name: str) -> None:
    existing = _existing_index_names(bind, table_name)
    for index_name, columns in SHARE_TASK_INDEXES:
        if index_name in existing:
            continue
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        _upgrade_postgresql_enum()
    elif dialect == "mysql":
        _upgrade_mysql_enum()

    if dialect in {"postgresql", "mysql"}:
        share_task_status_enum.create(bind, checkfirst=True)

    if not _table_exists(bind, SHARE_TASK_TABLE):
        op.create_table(
            SHARE_TASK_TABLE,
            sa.Column("id", id_pk_type, primary_key=True, autoincrement=True),
            sa.Column("user_id", id_pk_type, sa.ForeignKey("users.id"), nullable=False),
            sa.Column("platform", sa.String(length=32), nullable=False),
            sa.Column("reward_credits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "status",
                share_task_status_enum if dialect in {"postgresql", "mysql"} else sa.String(length=16),
                nullable=False,
                server_default="PENDING",
            ),
            sa.Column("screenshot_path", sa.String(length=500), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("share_text", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("review_note", sa.String(length=255), nullable=True),
            sa.Column("reviewed_by", id_pk_type, sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("user_id", "platform", name="uk_user_share_task_platform"),
        )
    _create_missing_indexes(bind, SHARE_TASK_TABLE)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if _table_exists(bind, SHARE_TASK_TABLE):
        existing_indexes = _existing_index_names(bind, SHARE_TASK_TABLE)
        for index_name, _columns in reversed(SHARE_TASK_INDEXES):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name=SHARE_TASK_TABLE)
        op.drop_table(SHARE_TASK_TABLE)

    if dialect == "postgresql":
        _downgrade_postgresql_enum(bind)
    elif dialect == "mysql":
        _downgrade_mysql_enum()
