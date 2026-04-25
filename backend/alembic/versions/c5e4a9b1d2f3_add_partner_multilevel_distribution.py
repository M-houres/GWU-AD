"""add partner multilevel distribution fields

Revision ID: c5e4a9b1d2f3
Revises: f9e8d7c6b5a4
Create Date: 2026-04-24 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c5e4a9b1d2f3"
down_revision = "f9e8d7c6b5a4"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {str(item.get("name")) for item in inspector.get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    try:
        return {str(item.get("name")) for item in inspector.get_indexes(table_name) if item.get("name")}
    except Exception:
        return set()


def upgrade() -> None:
    bind = op.get_bind()

    partner_channel_cols = _column_names(bind, "partner_channels")
    if "parent_channel_id" not in partner_channel_cols:
        op.add_column("partner_channels", sa.Column("parent_channel_id", sa.Integer(), nullable=True))
    if "root_channel_id" not in partner_channel_cols:
        op.add_column("partner_channels", sa.Column("root_channel_id", sa.Integer(), nullable=True))
    if "level" not in partner_channel_cols:
        op.add_column("partner_channels", sa.Column("level", sa.Integer(), nullable=False, server_default="1"))

    partner_binding_cols = _column_names(bind, "partner_user_bindings")
    if "locked_at" not in partner_binding_cols:
        op.add_column("partner_user_bindings", sa.Column("locked_at", sa.DateTime(), nullable=True))

    partner_attr_cols = _column_names(bind, "partner_order_attributions")
    if "root_channel_id" not in partner_attr_cols:
        op.add_column("partner_order_attributions", sa.Column("root_channel_id", sa.Integer(), nullable=True))
    if "root_channel_code_snapshot" not in partner_attr_cols:
        op.add_column("partner_order_attributions", sa.Column("root_channel_code_snapshot", sa.String(length=32), nullable=False, server_default=""))
    if "channel_level" not in partner_attr_cols:
        op.add_column("partner_order_attributions", sa.Column("channel_level", sa.Integer(), nullable=False, server_default="1"))

    partner_ledger_cols = _column_names(bind, "partner_rebate_ledger")
    if "source_channel_id" not in partner_ledger_cols:
        op.add_column("partner_rebate_ledger", sa.Column("source_channel_id", sa.Integer(), nullable=True))
    if "rebate_rate_bp" not in partner_ledger_cols:
        op.add_column("partner_rebate_ledger", sa.Column("rebate_rate_bp", sa.Integer(), nullable=False, server_default="0"))
    if "source_channel_code_snapshot" not in partner_ledger_cols:
        op.add_column("partner_rebate_ledger", sa.Column("source_channel_code_snapshot", sa.String(length=32), nullable=False, server_default=""))

    op.execute("UPDATE partner_channels SET level = 1 WHERE level IS NULL")
    op.execute("UPDATE partner_channels SET root_channel_id = id WHERE root_channel_id IS NULL")
    op.execute("UPDATE partner_user_bindings SET locked_at = updated_at WHERE locked_at IS NULL")
    op.execute("UPDATE partner_order_attributions SET root_channel_id = channel_id WHERE root_channel_id IS NULL")
    op.execute("UPDATE partner_order_attributions SET root_channel_code_snapshot = channel_code_snapshot WHERE root_channel_code_snapshot = '' OR root_channel_code_snapshot IS NULL")
    op.execute("UPDATE partner_order_attributions SET channel_level = 1 WHERE channel_level IS NULL")
    op.execute("UPDATE partner_rebate_ledger SET source_channel_id = channel_id WHERE source_channel_id IS NULL")
    op.execute("UPDATE partner_rebate_ledger SET source_channel_code_snapshot = '' WHERE source_channel_code_snapshot IS NULL")

    partner_channel_indexes = _index_names(bind, "partner_channels")
    if "ix_partner_channels_parent_channel_id" not in partner_channel_indexes:
        op.create_index("ix_partner_channels_parent_channel_id", "partner_channels", ["parent_channel_id"])
    if "ix_partner_channels_root_channel_id" not in partner_channel_indexes:
        op.create_index("ix_partner_channels_root_channel_id", "partner_channels", ["root_channel_id"])
    if "ix_partner_channels_level" not in partner_channel_indexes:
        op.create_index("ix_partner_channels_level", "partner_channels", ["level"])

    partner_binding_indexes = _index_names(bind, "partner_user_bindings")
    if "ix_partner_user_bindings_locked_at" not in partner_binding_indexes:
        op.create_index("ix_partner_user_bindings_locked_at", "partner_user_bindings", ["locked_at"])

    partner_attr_indexes = _index_names(bind, "partner_order_attributions")
    if "ix_partner_order_attributions_root_channel_id" not in partner_attr_indexes:
        op.create_index("ix_partner_order_attributions_root_channel_id", "partner_order_attributions", ["root_channel_id"])
    if "ix_partner_order_attributions_root_channel_code_snapshot" not in partner_attr_indexes:
        op.create_index("ix_partner_order_attributions_root_channel_code_snapshot", "partner_order_attributions", ["root_channel_code_snapshot"])
    if "ix_partner_order_attributions_channel_level" not in partner_attr_indexes:
        op.create_index("ix_partner_order_attributions_channel_level", "partner_order_attributions", ["channel_level"])

    partner_ledger_indexes = _index_names(bind, "partner_rebate_ledger")
    if "ix_partner_rebate_ledger_source_channel_id" not in partner_ledger_indexes:
        op.create_index("ix_partner_rebate_ledger_source_channel_id", "partner_rebate_ledger", ["source_channel_id"])
    if "ix_partner_rebate_ledger_source_channel_code_snapshot" not in partner_ledger_indexes:
        op.create_index("ix_partner_rebate_ledger_source_channel_code_snapshot", "partner_rebate_ledger", ["source_channel_code_snapshot"])


def downgrade() -> None:
    bind = op.get_bind()

    partner_ledger_indexes = _index_names(bind, "partner_rebate_ledger")
    if "ix_partner_rebate_ledger_source_channel_code_snapshot" in partner_ledger_indexes:
        op.drop_index("ix_partner_rebate_ledger_source_channel_code_snapshot", table_name="partner_rebate_ledger")
    if "ix_partner_rebate_ledger_source_channel_id" in partner_ledger_indexes:
        op.drop_index("ix_partner_rebate_ledger_source_channel_id", table_name="partner_rebate_ledger")

    partner_attr_indexes = _index_names(bind, "partner_order_attributions")
    if "ix_partner_order_attributions_channel_level" in partner_attr_indexes:
        op.drop_index("ix_partner_order_attributions_channel_level", table_name="partner_order_attributions")
    if "ix_partner_order_attributions_root_channel_code_snapshot" in partner_attr_indexes:
        op.drop_index("ix_partner_order_attributions_root_channel_code_snapshot", table_name="partner_order_attributions")
    if "ix_partner_order_attributions_root_channel_id" in partner_attr_indexes:
        op.drop_index("ix_partner_order_attributions_root_channel_id", table_name="partner_order_attributions")

    partner_binding_indexes = _index_names(bind, "partner_user_bindings")
    if "ix_partner_user_bindings_locked_at" in partner_binding_indexes:
        op.drop_index("ix_partner_user_bindings_locked_at", table_name="partner_user_bindings")

    partner_channel_indexes = _index_names(bind, "partner_channels")
    if "ix_partner_channels_level" in partner_channel_indexes:
        op.drop_index("ix_partner_channels_level", table_name="partner_channels")
    if "ix_partner_channels_root_channel_id" in partner_channel_indexes:
        op.drop_index("ix_partner_channels_root_channel_id", table_name="partner_channels")
    if "ix_partner_channels_parent_channel_id" in partner_channel_indexes:
        op.drop_index("ix_partner_channels_parent_channel_id", table_name="partner_channels")

    partner_ledger_cols = _column_names(bind, "partner_rebate_ledger")
    if "source_channel_code_snapshot" in partner_ledger_cols:
        op.drop_column("partner_rebate_ledger", "source_channel_code_snapshot")
    if "rebate_rate_bp" in partner_ledger_cols:
        op.drop_column("partner_rebate_ledger", "rebate_rate_bp")
    if "source_channel_id" in partner_ledger_cols:
        op.drop_column("partner_rebate_ledger", "source_channel_id")

    partner_attr_cols = _column_names(bind, "partner_order_attributions")
    if "channel_level" in partner_attr_cols:
        op.drop_column("partner_order_attributions", "channel_level")
    if "root_channel_code_snapshot" in partner_attr_cols:
        op.drop_column("partner_order_attributions", "root_channel_code_snapshot")
    if "root_channel_id" in partner_attr_cols:
        op.drop_column("partner_order_attributions", "root_channel_id")

    partner_binding_cols = _column_names(bind, "partner_user_bindings")
    if "locked_at" in partner_binding_cols:
        op.drop_column("partner_user_bindings", "locked_at")

    partner_channel_cols = _column_names(bind, "partner_channels")
    if "level" in partner_channel_cols:
        op.drop_column("partner_channels", "level")
    if "root_channel_id" in partner_channel_cols:
        op.drop_column("partner_channels", "root_channel_id")
    if "parent_channel_id" in partner_channel_cols:
        op.drop_column("partner_channels", "parent_channel_id")
