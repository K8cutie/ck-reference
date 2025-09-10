"""Add org/unit scope to GL: journal_entries, gl_period_locks

- Adds org_id & unit_id with FKs
- Backfills existing rows to 'DIO-DEFAULT' / 'PAR-DEFAULT'
- Adds covering indexes for org dashboards
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "c2d3e4f5a6b7"
down_revision = "f7a1e2c3d4e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("journal_entries", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("journal_entries", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    op.add_column("gl_period_locks", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("gl_period_locks", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_journal_entries_org",
        "journal_entries",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_journal_entries_unit",
        "journal_entries",
        "org_units",
        ["unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_gl_period_locks_org",
        "gl_period_locks",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_gl_period_locks_unit",
        "gl_period_locks",
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

        WITH org AS (
            SELECT id FROM organizations WHERE code = 'DIO-DEFAULT' LIMIT 1
        )
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
        UPDATE journal_entries je
        SET org_id = d.org_id,
            unit_id = d.unit_id
        FROM d
        WHERE je.org_id IS NULL OR je.unit_id IS NULL;
        """
    )
    op.execute(
        """
        WITH d AS (
            SELECT o.id AS org_id, u.id AS unit_id
            FROM organizations o
            JOIN org_units u ON u.org_id = o.id
            WHERE o.code = 'DIO-DEFAULT' AND u.code = 'PAR-DEFAULT'
            LIMIT 1
        )
        UPDATE gl_period_locks gpl
        SET org_id = d.org_id,
            unit_id = d.unit_id
        FROM d
        WHERE gpl.org_id IS NULL OR gpl.unit_id IS NULL;
        """
    )

    # 5) Tighten to NOT NULL
    op.alter_column("journal_entries", "org_id", nullable=False)
    op.alter_column("journal_entries", "unit_id", nullable=False)
    op.alter_column("gl_period_locks", "org_id", nullable=False)
    op.alter_column("gl_period_locks", "unit_id", nullable=False)

    # 6) Covering indexes
    op.create_index(
        "ix_journal_entries_org_unit_entry_date",
        "journal_entries",
        ["org_id", "unit_id", "entry_date"],
        unique=False,
    )
    op.create_index(
        "ix_gl_period_locks_org_unit_period_month",
        "gl_period_locks",
        ["org_id", "unit_id", "period_month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_gl_period_locks_org_unit_period_month", table_name="gl_period_locks")
    op.drop_index("ix_journal_entries_org_unit_entry_date", table_name="journal_entries")

    op.drop_constraint("fk_gl_period_locks_unit", "gl_period_locks", type_="foreignkey")
    op.drop_constraint("fk_gl_period_locks_org", "gl_period_locks", type_="foreignkey")
    op.drop_constraint("fk_journal_entries_unit", "journal_entries", type_="foreignkey")
    op.drop_constraint("fk_journal_entries_org", "journal_entries", type_="foreignkey")

    op.drop_column("gl_period_locks", "unit_id")
    op.drop_column("gl_period_locks", "org_id")
    op.drop_column("journal_entries", "unit_id")
    op.drop_column("journal_entries", "org_id")
