"""gl_period_locks: month-level locks for posted journals

Revision ID: 4b7f1c2d9e00
Revises: 3a1f2c9d7ab0
Create Date: 2025-08-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4b7f1c2d9e00"
down_revision = "3a1f2c9d7ab0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gl_period_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        # First day of the locked month (e.g., 2025-08-01). Unique per month.
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("period_month", name="uq_gl_period_locks_period_month"),
    )
    op.create_index(
        "ix_gl_period_locks_period_month", "gl_period_locks", ["period_month"], unique=False
    )
    op.create_index(
        "ix_gl_period_locks_is_locked", "gl_period_locks", ["is_locked"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_gl_period_locks_is_locked", table_name="gl_period_locks")
    op.drop_index("ix_gl_period_locks_period_month", table_name="gl_period_locks")
    op.drop_table("gl_period_locks")
