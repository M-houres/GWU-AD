"""change order amount to numeric

Revision ID: f1a2b3c4d5e6
Revises: c3d9e1f7a2b4
Create Date: 2026-04-13 11:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "c3d9e1f7a2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE orders SET amount_cny = ROUND(amount_cny, 2)")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column(
            "amount_cny",
            existing_type=sa.Float(),
            type_=sa.Numeric(10, 2),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.alter_column(
            "amount_cny",
            existing_type=sa.Numeric(10, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )
