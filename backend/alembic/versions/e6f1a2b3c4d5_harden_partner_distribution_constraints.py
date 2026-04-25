"""harden partner distribution constraints

Revision ID: e6f1a2b3c4d5
Revises: d4f6e8a1b2c3
Create Date: 2026-04-25 18:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f1a2b3c4d5"
down_revision: Union[str, None] = "d4f6e8a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _constraint_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    names: set[str] = set()
    try:
        for item in inspector.get_foreign_keys(table_name):
            name = str(item.get("name") or "").strip()
            if name:
                names.add(name)
    except Exception:
        pass
    try:
        for item in inspector.get_check_constraints(table_name):
            name = str(item.get("name") or "").strip()
            if name:
                names.add(name)
    except Exception:
        pass
    return names


def _existing_indexes(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    try:
        return {str(item.get("name")) for item in inspector.get_indexes(table_name) if item.get("name")}
    except Exception:
        return set()


def _column_type_map(bind, table_name: str) -> dict[str, sa.types.TypeEngine]:
    inspector = sa.inspect(bind)
    try:
        return {str(item.get("name")): item.get("type") for item in inspector.get_columns(table_name)}
    except Exception:
        return {}


def _looks_like_bigint(column_type: sa.types.TypeEngine | None) -> bool:
    if column_type is None:
        return False
    return "BIGINT" in str(column_type).upper()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    column_types = {
        "partner_channels": _column_type_map(bind, "partner_channels"),
        "partner_order_attributions": _column_type_map(bind, "partner_order_attributions"),
        "partner_rebate_ledger": _column_type_map(bind, "partner_rebate_ledger"),
    }

    if dialect == "mysql":
        if not _looks_like_bigint(column_types["partner_channels"].get("parent_channel_id")):
            op.alter_column(
                "partner_channels",
                "parent_channel_id",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )
        if not _looks_like_bigint(column_types["partner_channels"].get("root_channel_id")):
            op.alter_column(
                "partner_channels",
                "root_channel_id",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )
        if not _looks_like_bigint(column_types["partner_order_attributions"].get("root_channel_id")):
            op.alter_column(
                "partner_order_attributions",
                "root_channel_id",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )
        if not _looks_like_bigint(column_types["partner_rebate_ledger"].get("source_channel_id")):
            op.alter_column(
                "partner_rebate_ledger",
                "source_channel_id",
                existing_type=sa.Integer(),
                type_=sa.BigInteger(),
                existing_nullable=True,
            )

    op.execute(
        """
        UPDATE partner_channels
        SET parent_channel_id = NULL
        WHERE parent_channel_id = id
           OR parent_channel_id NOT IN (
               SELECT id FROM (
                   SELECT id FROM partner_channels
               ) AS partner_channel_ids
           )
        """
    )
    op.execute(
        """
        UPDATE partner_channels
        SET root_channel_id = id
        WHERE root_channel_id IS NULL
           OR root_channel_id NOT IN (
               SELECT id FROM (
                   SELECT id FROM partner_channels
               ) AS partner_channel_ids
           )
        """
    )
    op.execute(
        """
        UPDATE partner_channels
        SET level = CASE
            WHEN level IS NULL OR level < 1 THEN 1
            WHEN level > 3 THEN 3
            ELSE level
        END
        """
    )
    op.execute(
        """
        UPDATE partner_channels
        SET default_rebate_rate_bp = CASE
            WHEN default_rebate_rate_bp IS NULL OR default_rebate_rate_bp < 0 THEN 0
            WHEN default_rebate_rate_bp > 10000 THEN 10000
            ELSE default_rebate_rate_bp
        END
        """
    )
    op.execute(
        """
        UPDATE partner_policies
        SET rebate_rate_bp = CASE
            WHEN rebate_rate_bp IS NULL OR rebate_rate_bp < 0 THEN 0
            WHEN rebate_rate_bp > 10000 THEN 10000
            ELSE rebate_rate_bp
        END
        """
    )
    op.execute(
        """
        UPDATE partner_order_attributions
        SET root_channel_id = channel_id
        WHERE root_channel_id IS NULL
           OR root_channel_id NOT IN (SELECT id FROM partner_channels)
        """
    )
    op.execute(
        """
        UPDATE partner_order_attributions
        SET channel_level = CASE
            WHEN channel_level IS NULL OR channel_level < 1 THEN 1
            WHEN channel_level > 3 THEN 3
            ELSE channel_level
        END
        """
    )
    op.execute(
        """
        UPDATE partner_order_attributions
        SET rebate_rate_bp = CASE
            WHEN rebate_rate_bp IS NULL OR rebate_rate_bp < 0 THEN 0
            WHEN rebate_rate_bp > 10000 THEN 10000
            ELSE rebate_rate_bp
        END
        """
    )
    op.execute(
        """
        UPDATE partner_rebate_ledger
        SET source_channel_id = channel_id
        WHERE source_channel_id IS NOT NULL
          AND source_channel_id NOT IN (SELECT id FROM partner_channels)
        """
    )
    op.execute(
        """
        UPDATE partner_rebate_ledger
        SET rebate_rate_bp = CASE
            WHEN rebate_rate_bp IS NULL OR rebate_rate_bp < 0 THEN 0
            WHEN rebate_rate_bp > 10000 THEN 10000
            ELSE rebate_rate_bp
        END
        """
    )
    op.execute(
        """
        UPDATE partner_rebate_ledger
        SET base_amount_fen = CASE
            WHEN base_amount_fen IS NULL OR base_amount_fen < 0 THEN 0
            ELSE base_amount_fen
        END
        """
    )
    op.execute(
        """
        UPDATE partner_withdraw_requests
        SET apply_amount_fen = CASE
            WHEN apply_amount_fen IS NULL OR apply_amount_fen < 0 THEN 0
            ELSE apply_amount_fen
        END
        """
    )

    existing_constraints = {
        "partner_channels": _constraint_names(bind, "partner_channels"),
        "partner_policies": _constraint_names(bind, "partner_policies"),
        "partner_order_attributions": _constraint_names(bind, "partner_order_attributions"),
        "partner_rebate_ledger": _constraint_names(bind, "partner_rebate_ledger"),
        "partner_withdraw_requests": _constraint_names(bind, "partner_withdraw_requests"),
    }

    if dialect != "sqlite":
        if "fk_partner_channels_parent_channel_id_partner_channels" not in existing_constraints["partner_channels"]:
            op.create_foreign_key(
                "fk_partner_channels_parent_channel_id_partner_channels",
                "partner_channels",
                "partner_channels",
                ["parent_channel_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_partner_channels_root_channel_id_partner_channels" not in existing_constraints["partner_channels"]:
            op.create_foreign_key(
                "fk_partner_channels_root_channel_id_partner_channels",
                "partner_channels",
                "partner_channels",
                ["root_channel_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_partner_order_attr_root_channel_id_partner_channels" not in existing_constraints["partner_order_attributions"]:
            op.create_foreign_key(
                "fk_partner_order_attr_root_channel_id_partner_channels",
                "partner_order_attributions",
                "partner_channels",
                ["root_channel_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "fk_partner_ledger_source_channel_id_partner_channels" not in existing_constraints["partner_rebate_ledger"]:
            op.create_foreign_key(
                "fk_partner_ledger_source_channel_id_partner_channels",
                "partner_rebate_ledger",
                "partner_channels",
                ["source_channel_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "ck_partner_channels_level_range" not in existing_constraints["partner_channels"]:
        op.create_check_constraint(
            "ck_partner_channels_level_range",
            "partner_channels",
            "level >= 1 AND level <= 3",
        )
    if "ck_partner_channels_default_rate_range" not in existing_constraints["partner_channels"]:
        op.create_check_constraint(
            "ck_partner_channels_default_rate_range",
            "partner_channels",
            "default_rebate_rate_bp >= 0 AND default_rebate_rate_bp <= 10000",
        )
    if dialect != "mysql" and "ck_partner_channels_parent_not_self" not in existing_constraints["partner_channels"]:
        op.create_check_constraint(
            "ck_partner_channels_parent_not_self",
            "partner_channels",
            "parent_channel_id IS NULL OR parent_channel_id <> id",
        )
    if "ck_partner_policies_rate_range" not in existing_constraints["partner_policies"]:
        op.create_check_constraint(
            "ck_partner_policies_rate_range",
            "partner_policies",
            "rebate_rate_bp >= 0 AND rebate_rate_bp <= 10000",
        )
    if "ck_partner_order_attr_level_range" not in existing_constraints["partner_order_attributions"]:
        op.create_check_constraint(
            "ck_partner_order_attr_level_range",
            "partner_order_attributions",
            "channel_level >= 1 AND channel_level <= 3",
        )
    if "ck_partner_order_attr_rate_range" not in existing_constraints["partner_order_attributions"]:
        op.create_check_constraint(
            "ck_partner_order_attr_rate_range",
            "partner_order_attributions",
            "rebate_rate_bp >= 0 AND rebate_rate_bp <= 10000",
        )
    if "ck_partner_ledger_rate_range" not in existing_constraints["partner_rebate_ledger"]:
        op.create_check_constraint(
            "ck_partner_ledger_rate_range",
            "partner_rebate_ledger",
            "rebate_rate_bp >= 0 AND rebate_rate_bp <= 10000",
        )
    if "ck_partner_ledger_base_amount_nonnegative" not in existing_constraints["partner_rebate_ledger"]:
        op.create_check_constraint(
            "ck_partner_ledger_base_amount_nonnegative",
            "partner_rebate_ledger",
            "base_amount_fen >= 0",
        )
    if "ck_partner_withdraw_amount_nonnegative" not in existing_constraints["partner_withdraw_requests"]:
        op.create_check_constraint(
            "ck_partner_withdraw_amount_nonnegative",
            "partner_withdraw_requests",
            "apply_amount_fen >= 0",
        )

    partner_channel_indexes = _existing_indexes(bind, "partner_channels")
    if "ix_partner_channels_parent_channel_id" not in partner_channel_indexes:
        op.create_index("ix_partner_channels_parent_channel_id", "partner_channels", ["parent_channel_id"])
    if "ix_partner_channels_root_channel_id" not in partner_channel_indexes:
        op.create_index("ix_partner_channels_root_channel_id", "partner_channels", ["root_channel_id"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    for table_name, constraint_name, constraint_type in [
        ("partner_withdraw_requests", "ck_partner_withdraw_amount_nonnegative", "check"),
        ("partner_rebate_ledger", "ck_partner_ledger_base_amount_nonnegative", "check"),
        ("partner_rebate_ledger", "ck_partner_ledger_rate_range", "check"),
        ("partner_order_attributions", "ck_partner_order_attr_rate_range", "check"),
        ("partner_order_attributions", "ck_partner_order_attr_level_range", "check"),
        ("partner_policies", "ck_partner_policies_rate_range", "check"),
        ("partner_channels", "ck_partner_channels_parent_not_self", "check"),
        ("partner_channels", "ck_partner_channels_default_rate_range", "check"),
        ("partner_channels", "ck_partner_channels_level_range", "check"),
    ]:
        names = _constraint_names(bind, table_name)
        if constraint_name in names:
            op.drop_constraint(constraint_name, table_name, type_=constraint_type)

    if dialect != "sqlite":
        for table_name, constraint_name in [
            ("partner_rebate_ledger", "fk_partner_ledger_source_channel_id_partner_channels"),
            ("partner_order_attributions", "fk_partner_order_attr_root_channel_id_partner_channels"),
            ("partner_channels", "fk_partner_channels_root_channel_id_partner_channels"),
            ("partner_channels", "fk_partner_channels_parent_channel_id_partner_channels"),
        ]:
            names = _constraint_names(bind, table_name)
            if constraint_name in names:
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
