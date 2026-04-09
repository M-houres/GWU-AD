"""add recent lookup indexes

Revision ID: d6c2e9a1f4b8
Revises: e1a9c4d8b7f3
Create Date: 2026-04-09 09:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d6c2e9a1f4b8"
down_revision: Union[str, None] = "e1a9c4d8b7f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_indexes(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {item["name"] for item in inspector.get_indexes(table_name)}


def upgrade() -> None:
    task_indexes = _existing_indexes("tasks")
    if "ix_tasks_user_recent" not in task_indexes:
        op.create_index("ix_tasks_user_recent", "tasks", ["user_id", "id"], unique=False)

    credit_indexes = _existing_indexes("credit_transactions")
    if "ix_credit_transactions_user_recent" not in credit_indexes:
        op.create_index(
            "ix_credit_transactions_user_recent",
            "credit_transactions",
            ["user_id", "id"],
            unique=False,
        )


def downgrade() -> None:
    task_indexes = _existing_indexes("tasks")
    if "ix_tasks_user_recent" in task_indexes:
        op.drop_index("ix_tasks_user_recent", table_name="tasks")

    credit_indexes = _existing_indexes("credit_transactions")
    if "ix_credit_transactions_user_recent" in credit_indexes:
        op.drop_index("ix_credit_transactions_user_recent", table_name="credit_transactions")
