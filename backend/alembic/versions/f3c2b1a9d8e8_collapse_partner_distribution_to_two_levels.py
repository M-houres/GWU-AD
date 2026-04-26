"""collapse partner distribution to two levels

Revision ID: f3c2b1a9d8e8
Revises: f1a2b3c4d5e7
Create Date: 2026-04-27 10:48:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3c2b1a9d8e8"
down_revision: Union[str, None] = "f1a2b3c4d5e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _constraint_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    names: set[str] = set()
    try:
        for item in inspector.get_check_constraints(table_name):
            name = str(item.get("name") or "").strip()
            if name:
                names.add(name)
    except Exception:
        pass
    return names


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            """
            UPDATE partner_channels
            LEFT JOIN partner_channels AS parent
              ON parent.id = partner_channels.parent_channel_id
            SET partner_channels.root_channel_id = COALESCE(
                NULLIF(partner_channels.root_channel_id, partner_channels.id),
                NULLIF(parent.root_channel_id, partner_channels.id),
                NULLIF(parent.id, partner_channels.id),
                partner_channels.id
            )
            WHERE COALESCE(partner_channels.level, 1) > 2
            """
        )
    else:
        op.execute(
            """
            UPDATE partner_channels
            SET root_channel_id = COALESCE(
                NULLIF(root_channel_id, id),
                (
                    SELECT COALESCE(
                        NULLIF(parent.root_channel_id, partner_channels.id),
                        NULLIF(parent.id, partner_channels.id)
                    )
                    FROM partner_channels AS parent
                    WHERE parent.id = partner_channels.parent_channel_id
                ),
                id
            )
            WHERE COALESCE(level, 1) > 2
            """
        )
    op.execute(
        """
        UPDATE partner_channels
        SET parent_channel_id = CASE
                WHEN root_channel_id IS NULL OR root_channel_id = id THEN NULL
                ELSE root_channel_id
            END,
            level = CASE
                WHEN root_channel_id IS NULL OR root_channel_id = id THEN 1
                ELSE 2
            END
        WHERE COALESCE(level, 1) > 2
        """
    )
    op.execute(
        """
        UPDATE partner_channels
        SET level = CASE
            WHEN level IS NULL OR level < 1 THEN 1
            WHEN level > 2 THEN 2
            ELSE level
        END
        """
    )
    op.execute(
        """
        UPDATE partner_channels
        SET parent_channel_id = NULL,
            root_channel_id = id
        WHERE level = 1
        """
    )
    if dialect == "mysql":
        op.execute(
            """
            UPDATE partner_channels
            LEFT JOIN partner_channels AS parent
              ON parent.id = partner_channels.parent_channel_id
            SET partner_channels.root_channel_id = COALESCE(
                CASE
                    WHEN parent.level = 1 THEN parent.id
                    ELSE COALESCE(NULLIF(parent.root_channel_id, partner_channels.id), parent.id)
                END,
                NULLIF(partner_channels.root_channel_id, partner_channels.id),
                partner_channels.id
            )
            WHERE partner_channels.level = 2
            """
        )
    else:
        op.execute(
            """
            UPDATE partner_channels
            SET root_channel_id = COALESCE(
                    (
                        SELECT CASE
                            WHEN parent.level = 1 THEN parent.id
                            ELSE COALESCE(NULLIF(parent.root_channel_id, partner_channels.id), parent.id)
                        END
                        FROM partner_channels AS parent
                        WHERE parent.id = partner_channels.parent_channel_id
                    ),
                    NULLIF(root_channel_id, id),
                    id
                )
            WHERE level = 2
            """
        )
    op.execute(
        """
        UPDATE partner_channels
        SET parent_channel_id = CASE
                WHEN root_channel_id IS NULL OR root_channel_id = id THEN NULL
                ELSE root_channel_id
            END
        WHERE level = 2
        """
    )

    op.execute(
        """
        UPDATE partner_order_attributions
        SET root_channel_id = COALESCE(
                (
                    SELECT COALESCE(channel.root_channel_id, channel.id)
                    FROM partner_channels AS channel
                    WHERE channel.id = partner_order_attributions.channel_id
                ),
                root_channel_id,
                channel_id
            )
        """
    )
    op.execute(
        """
        UPDATE partner_order_attributions
        SET root_channel_code_snapshot = COALESCE(
                (
                    SELECT root.channel_code
                    FROM partner_channels AS channel
                    LEFT JOIN partner_channels AS root
                      ON root.id = COALESCE(channel.root_channel_id, channel.id)
                    WHERE channel.id = partner_order_attributions.channel_id
                ),
                NULLIF(root_channel_code_snapshot, ''),
                channel_code_snapshot
            )
        """
    )
    op.execute(
        """
        UPDATE partner_order_attributions
        SET channel_level = COALESCE(
                (
                    SELECT CASE
                        WHEN COALESCE(channel.level, 1) <= 1 THEN 1
                        ELSE 2
                    END
                    FROM partner_channels AS channel
                    WHERE channel.id = partner_order_attributions.channel_id
                ),
                CASE
                    WHEN channel_level IS NULL OR channel_level < 1 THEN 1
                    WHEN channel_level > 2 THEN 2
                    ELSE channel_level
                END
            )
        """
    )

    if dialect != "sqlite":
        existing_channel_constraints = _constraint_names(bind, "partner_channels")
        if "ck_partner_channels_level_range" in existing_channel_constraints:
            op.drop_constraint("ck_partner_channels_level_range", "partner_channels", type_="check")
        op.create_check_constraint(
            "ck_partner_channels_level_range",
            "partner_channels",
            "level >= 1 AND level <= 2",
        )

        existing_attr_constraints = _constraint_names(bind, "partner_order_attributions")
        if "ck_partner_order_attr_level_range" in existing_attr_constraints:
            op.drop_constraint("ck_partner_order_attr_level_range", "partner_order_attributions", type_="check")
        op.create_check_constraint(
            "ck_partner_order_attr_level_range",
            "partner_order_attributions",
            "channel_level >= 1 AND channel_level <= 2",
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect != "sqlite":
        existing_channel_constraints = _constraint_names(bind, "partner_channels")
        if "ck_partner_channels_level_range" in existing_channel_constraints:
            op.drop_constraint("ck_partner_channels_level_range", "partner_channels", type_="check")
        op.create_check_constraint(
            "ck_partner_channels_level_range",
            "partner_channels",
            "level >= 1 AND level <= 3",
        )

        existing_attr_constraints = _constraint_names(bind, "partner_order_attributions")
        if "ck_partner_order_attr_level_range" in existing_attr_constraints:
            op.drop_constraint("ck_partner_order_attr_level_range", "partner_order_attributions", type_="check")
        op.create_check_constraint(
            "ck_partner_order_attr_level_range",
            "partner_order_attributions",
            "channel_level >= 1 AND channel_level <= 3",
        )
