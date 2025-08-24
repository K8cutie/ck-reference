"""calendar: add events tables (scope B)

Revision ID: 77c6958025b9
Revises: a3580ebee122
Create Date: 2025-08-09 14:50:34.481557

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "77c6958025b9"
down_revision: Union[str, Sequence[str], None] = "a3580ebee122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create calendar_events."""
    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),

        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),

        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Asia/Manila'")),

        # iCalendar RRULE, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR"
        sa.Column("rrule", sa.Text(), nullable=True),

        # Exception dates to skip specific recurrences
        sa.Column(
            "exdates",
            postgresql.ARRAY(sa.DateTime(timezone=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::timestamptz[]"),
        ),

        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),

        sa.CheckConstraint("end_at >= start_at", name="calendar_events_end_after_start"),
    )

    op.create_index("ix_calendar_events_start_at", "calendar_events", ["start_at"])
    op.create_index("ix_calendar_events_end_at", "calendar_events", ["end_at"])


def downgrade() -> None:
    """Downgrade schema: drop calendar_events and indexes."""
    op.drop_index("ix_calendar_events_end_at", table_name="calendar_events")
    op.drop_index("ix_calendar_events_start_at", table_name="calendar_events")
    op.drop_table("calendar_events")
