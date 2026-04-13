"""expand task status enum for preprocessing queue

Revision ID: c3d9e1f7a2b4
Revises: b8e4a1f2c9d7
Create Date: 2026-04-12 02:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d9e1f7a2b4"
down_revision = "b8e4a1f2c9d7"
branch_labels = None
depends_on = None


OLD_TASK_STATUS_VALUES = ("PENDING", "RUNNING", "COMPLETED", "FAILED")
NEW_TASK_STATUS_VALUES = ("PENDING", "PREPROCESSING", "QUEUED", "RUNNING", "COMPLETED", "FAILED")

old_task_status_enum = sa.Enum(*OLD_TASK_STATUS_VALUES, name="taskstatus")
new_task_status_enum = sa.Enum(*NEW_TASK_STATUS_VALUES, name="taskstatus")


def _upgrade_postgresql_enum() -> None:
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'PREPROCESSING'")
    op.execute("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'QUEUED'")


def _downgrade_postgresql_enum(bind) -> None:
    op.execute("UPDATE tasks SET status = 'PENDING' WHERE status IN ('PREPROCESSING', 'QUEUED')")
    op.execute("ALTER TYPE taskstatus RENAME TO taskstatus_old")
    old_task_status_enum.create(bind, checkfirst=False)
    op.execute(
        """
        ALTER TABLE tasks
        ALTER COLUMN status TYPE taskstatus
        USING (
            CASE
                WHEN status::text IN ('PREPROCESSING', 'QUEUED') THEN 'PENDING'
                ELSE status::text
            END
        )::taskstatus
        """
    )
    op.execute("DROP TYPE taskstatus_old")


def _upgrade_mysql_enum() -> None:
    op.alter_column(
        "tasks",
        "status",
        existing_type=old_task_status_enum,
        type_=new_task_status_enum,
        existing_nullable=False,
    )


def _downgrade_mysql_enum() -> None:
    op.execute("UPDATE tasks SET status = 'PENDING' WHERE status IN ('PREPROCESSING', 'QUEUED')")
    op.alter_column(
        "tasks",
        "status",
        existing_type=new_task_status_enum,
        type_=old_task_status_enum,
        existing_nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        _upgrade_postgresql_enum()
        return
    if dialect == "mysql":
        _upgrade_mysql_enum()


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        _downgrade_postgresql_enum(bind)
        return
    if dialect == "mysql":
        _downgrade_mysql_enum()
