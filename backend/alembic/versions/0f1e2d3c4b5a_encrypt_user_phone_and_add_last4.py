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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {str(col.get("name")) for col in inspector.get_columns("users")}
    user_indexes = {str(idx.get("name")) for idx in inspector.get_indexes("users") if idx.get("name")}
    has_phone_last4 = "phone_last4" in user_columns

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)
        if not has_phone_last4:
            batch_op.add_column(sa.Column("phone_last4", sa.String(length=4), nullable=False, server_default=""))
            has_phone_last4 = True
        if "ix_users_phone_last4" not in user_indexes:
            batch_op.create_index("ix_users_phone_last4", ["phone_last4"], unique=False)

    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=20), type_=sa.String(length=128), existing_nullable=False)

    if has_phone_last4:
        bind.execute(sa.text("UPDATE users SET phone_last4 = substr(phone, length(phone) - 3, 4) WHERE phone IS NOT NULL AND phone != ''"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {str(col.get("name")) for col in inspector.get_columns("users")}
    user_indexes = {str(idx.get("name")) for idx in inspector.get_indexes("users") if idx.get("name")}

    with op.batch_alter_table("registration_risk_logs") as batch_op:
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)

    with op.batch_alter_table("users") as batch_op:
        if "ix_users_phone_last4" in user_indexes:
            batch_op.drop_index("ix_users_phone_last4")
        if "phone_last4" in user_columns:
            batch_op.drop_column("phone_last4")
        batch_op.alter_column("phone", existing_type=sa.String(length=128), type_=sa.String(length=20), existing_nullable=False)
