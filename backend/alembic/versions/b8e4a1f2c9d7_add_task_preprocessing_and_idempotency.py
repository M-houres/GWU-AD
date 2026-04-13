"""add task preprocessing and idempotency

Revision ID: b8e4a1f2c9d7
Revises: d6c2e9a1f4b8
Create Date: 2026-04-11 13:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b8e4a1f2c9d7"
down_revision = "d6c2e9a1f4b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=128), nullable=True))
        batch_op.create_unique_constraint("uk_tasks_user_idempotency_key", ["user_id", "idempotency_key"])
        batch_op.create_index("ix_tasks_status_id", ["status", "id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("ix_tasks_status_id")
        batch_op.drop_constraint("uk_tasks_user_idempotency_key", type_="unique")
        batch_op.drop_column("idempotency_key")
