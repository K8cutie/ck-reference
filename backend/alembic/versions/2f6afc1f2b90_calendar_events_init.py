"""calendar events init

Revision ID: 2f6afc1f2b90
Revises: 19624fe98afd
Create Date: 2025-08-10 14:20:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "2f6afc1f2b90"
down_revision = "19624fe98afd"  # update if your current head differs (run: alembic heads)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Asia/Manila'")),
        sa.Column("rrule", sa.Text(), nullable=True),
        sa.Column(
            "exdates",
            postgresql.ARRAY(sa.DateTime(timezone=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::timestamptz[]"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calendar_events_start_at", "calendar_events", ["start_at"])
    op.create_index("ix_calendar_events_end_at", "calendar_events", ["end_at"])
    op.create_index("ix_calendar_events_is_active", "calendar_events", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_calendar_events_is_active", table_name="calendar_events")
    op.drop_index("ix_calendar_events_end_at", table_name="calendar_events")
    op.drop_index("ix_calendar_events_start_at", table_name="calendar_events")
    op.drop_table("calendar_events")
