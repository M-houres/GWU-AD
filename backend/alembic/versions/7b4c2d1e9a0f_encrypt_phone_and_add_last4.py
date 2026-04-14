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
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)
        batch_op.add_column(sa.Column("phone_last4", sa.String(length=4), nullable=False, server_default=""))
        batch_op.create_index("ix_users_phone_last4", ["phone_last4"], unique=False)

    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET phone_last4 = substr(phone, length(phone) - 3, 4) WHERE phone IS NOT NULL AND phone != ''"))


def downgrade() -> None:
    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_phone_last4")
        batch_op.drop_column("phone_last4")
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)
