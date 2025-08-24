"""perf indexes for calendar & sigma"""
from alembic import op
import sqlalchemy as sa  # noqa

# Revision identifiers, used by Alembic.
revision = "8b6a1c23d4ef"
down_revision = "2f6afc1f2b90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Calendar: speed list/expand by active/time window, rrule presence, and exdates lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_events_active_time
        ON calendar_events (is_active, start_at, end_at);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_events_rrule_not_null
        ON calendar_events (start_at)
        WHERE rrule IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_calendar_events_exdates_gin
        ON calendar_events
        USING GIN (exdates);
    """)

    # Sigma: speed Pareto aggregations by process + period and category
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sigma_defects_proc_period
        ON sigma_defects (process, period_start, period_end);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_sigma_defects_proc_cat
        ON sigma_defects (process, category);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sigma_defects_proc_cat;")
    op.execute("DROP INDEX IF EXISTS ix_sigma_defects_proc_period;")
    op.execute("DROP INDEX IF EXISTS ix_calendar_events_exdates_gin;")
    op.execute("DROP INDEX IF EXISTS ix_calendar_events_rrule_not_null;")
    op.execute("DROP INDEX IF EXISTS ix_calendar_events_active_time;")
