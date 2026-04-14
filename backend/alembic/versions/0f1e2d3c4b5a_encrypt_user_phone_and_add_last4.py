"""encrypt user phone storage and add phone_last4

Revision ID: 0f1e2d3c4b5a
Revises: f9e8d7c6b5a4
Create Date: 2026-04-14 14:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f1e2d3c4b5a"
down_revision = "f9e8d7c6b5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)
        batch_op.add_column(sa.Column("phone_last4", sa.String(length=4), nullable=False, server_default=""))
        batch_op.create_index("ix_users_phone_last4", ["phone_last4"], unique=False)

    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)

    connection = op.get_bind()
    connection.execute(sa.text("UPDATE users SET phone_last4 = substr(phone, length(phone) - 3, 4) WHERE phone IS NOT NULL AND phone != ''"))


def downgrade() -> None:
    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_phone_last4")
        batch_op.drop_column("phone_last4")
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)
