"""add partner portal login fields

Revision ID: f1a2b3c4d5e7
Revises: e6f1a2b3c4d5
Create Date: 2026-04-25 22:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e7"
down_revision = "e6f1a2b3c4d5"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {str(item.get("name")) for item in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "partner_channels")
    if "portal_password_hash" not in column_names:
        op.add_column("partner_channels", sa.Column("portal_password_hash", sa.String(length=255), nullable=True))
    if "portal_password_updated_at" not in column_names:
        op.add_column("partner_channels", sa.Column("portal_password_updated_at", sa.DateTime(), nullable=True))
    if "portal_last_login_at" not in column_names:
        op.add_column("partner_channels", sa.Column("portal_last_login_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    column_names = _column_names(bind, "partner_channels")
    if "portal_last_login_at" in column_names:
        op.drop_column("partner_channels", "portal_last_login_at")
    if "portal_password_updated_at" in column_names:
        op.drop_column("partner_channels", "portal_password_updated_at")
    if "portal_password_hash" in column_names:
        op.drop_column("partner_channels", "portal_password_hash")
