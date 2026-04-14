"""encrypt phone column and add phone_last4

Revision ID: 7b4c2d1e9a0f
Revises: 0f1e2d3c4b5a
Create Date: 2026-04-14 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "7b4c2d1e9a0f"
down_revision = "0f1e2d3c4b5a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The previous revision 0f1e2d3c4b5a already applied the schema change.
    # Keep this revision as an intentional no-op so existing databases can
    # advance the Alembic head safely without replaying the same DDL twice.
    return None


def downgrade() -> None:
    return None
