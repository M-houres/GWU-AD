"""add order package snapshot

Revision ID: a9b8c7d6e5f4
Revises: 7b4c2d1e9a0f
Create Date: 2026-04-24 12:58:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a9b8c7d6e5f4"
down_revision = "7b4c2d1e9a0f"
branch_labels = None
depends_on = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    try:
        columns = inspector.get_columns(table_name)
    except Exception:
        return False
    return any(str(item.get("name")) == column_name for item in columns)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "orders", "package_snapshot"):
        op.add_column("orders", sa.Column("package_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "orders", "package_snapshot"):
        op.drop_column("orders", "package_snapshot")
