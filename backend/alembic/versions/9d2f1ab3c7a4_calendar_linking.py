"""calendar linking: origin/external_ref/meta

Revision ID: 9d2f1ab3c7a4
Revises: 8b6a1c23d4ef
Create Date: 2025-08-10 20:15:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "9d2f1ab3c7a4"
down_revision = "8b6a1c23d4ef"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("calendar_events", sa.Column("origin", sa.String(length=20), nullable=True))
    op.add_column("calendar_events", sa.Column("external_ref", sa.String(length=64), nullable=True))
    op.add_column(
        "calendar_events",
        sa.Column("meta", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index("ix_calendar_events_external_ref", "calendar_events", ["external_ref"], unique=False)
    # drop the temporary default so future inserts must set it explicitly
    op.execute("ALTER TABLE calendar_events ALTER COLUMN meta DROP DEFAULT")


def downgrade():
    op.drop_index("ix_calendar_events_external_ref", table_name="calendar_events")
    op.drop_column("calendar_events", "meta")
    op.drop_column("calendar_events", "external_ref")
    op.drop_column("calendar_events", "origin")
