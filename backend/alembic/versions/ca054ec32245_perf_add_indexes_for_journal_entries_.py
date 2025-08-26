"""perf: add indexes for journal_entries, journal_lines, gl_period_locks

Revision ID: ca054ec32245
Revises: 4b7f1c2d9e00
Create Date: 2025-08-26 23:41:19.812120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca054ec32245'
down_revision: Union[str, Sequence[str], None] = '4b7f1c2d9e00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add perf indexes (idempotent for Postgres)."""
    # journal_entries: commonly filtered by (is_locked, entry_date)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_journal_entries_is_locked_entry_date
        ON journal_entries (is_locked, entry_date);
    """)

    # journal_entries: quick lookups by reference_no (e.g., CLOSE-YYYYMM)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_journal_entries_reference_no
        ON journal_entries (reference_no);
    """)

    # journal_lines: fast join from entry -> lines
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_journal_lines_entry_id
        ON journal_lines (entry_id);
    """)

    # gl_period_locks: one-row-per-month lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_gl_period_locks_period_month
        ON gl_period_locks (period_month);
    """)


def downgrade() -> None:
    """Downgrade schema: drop perf indexes (if present)."""
    op.execute("DROP INDEX IF EXISTS ix_gl_period_locks_period_month;")
    op.execute("DROP INDEX IF EXISTS ix_journal_lines_entry_id;")
    op.execute("DROP INDEX IF EXISTS ix_journal_entries_reference_no;")
    op.execute("DROP INDEX IF EXISTS ix_journal_entries_is_locked_entry_date;")
