"""Add org/unit scope to calendar_events

- Adds org_id & unit_id with FKs
- Backfills existing rows to 'DIO-DEFAULT' / 'PAR-DEFAULT'
- Adds covering index for org-level queries
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("calendar_events", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("calendar_events", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_calendar_events_org",
        "calendar_events",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_calendar_events_unit",
        "calendar_events",
        "org_units",
        ["unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3) Ensure default org/unit exist (idempotent)
    op.execute(
        """
        INSERT INTO organizations(name, code)
        VALUES ('Default Diocese', 'DIO-DEFAULT')
        ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name;

        WITH org AS (SELECT id FROM organizations WHERE code = 'DIO-DEFAULT' LIMIT 1)
        INSERT INTO org_units(org_id, name, code, unit_type, is_active)
        SELECT org.id, 'Default Parish', 'PAR-DEFAULT', 'parish', TRUE
        FROM org
        WHERE NOT EXISTS (
            SELECT 1 FROM org_units u
            WHERE u.org_id = org.id AND u.code = 'PAR-DEFAULT'
        );
        """
    )

    # 4) Backfill existing rows to default scope
    op.execute(
        """
        WITH d AS (
            SELECT o.id AS org_id, u.id AS unit_id
            FROM organizations o
            JOIN org_units u ON u.org_id = o.id
            WHERE o.code = 'DIO-DEFAULT' AND u.code = 'PAR-DEFAULT'
            LIMIT 1
        )
        UPDATE calendar_events ce
        SET org_id = d.org_id,
            unit_id = d.unit_id
        FROM d
        WHERE ce.org_id IS NULL OR ce.unit_id IS NULL;
        """
    )

    # 5) Tighten to NOT NULL
    op.alter_column("calendar_events", "org_id", nullable=False)
    op.alter_column("calendar_events", "unit_id", nullable=False)

    # 6) Covering index (org/unit + start time)
    op.create_index(
        "ix_calendar_events_org_unit_start_at",
        "calendar_events",
        ["org_id", "unit_id", "start_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_calendar_events_org_unit_start_at", table_name="calendar_events")

    # Drop FKs
    op.drop_constraint("fk_calendar_events_unit", "calendar_events", type_="foreignkey")
    op.drop_constraint("fk_calendar_events_org", "calendar_events", type_="foreignkey")

    # Drop columns
    op.drop_column("calendar_events", "unit_id")
    op.drop_column("calendar_events", "org_id")
