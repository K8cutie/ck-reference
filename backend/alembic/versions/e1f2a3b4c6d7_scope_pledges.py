"""Add org/unit scope to pledges

- Adds org_id & unit_id with FKs
- Backfills existing rows to 'DIO-DEFAULT' / 'PAR-DEFAULT'
- Adds covering index for org-level queries
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "e1f2a3b4c6d7"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("pledges", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("pledges", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_pledges_org",
        "pledges",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_pledges_unit",
        "pledges",
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
        UPDATE pledges p
        SET org_id = d.org_id,
            unit_id = d.unit_id
        FROM d
        WHERE p.org_id IS NULL OR p.unit_id IS NULL;
        """
    )

    # 5) Tighten to NOT NULL
    op.alter_column("pledges", "org_id", nullable=False)
    op.alter_column("pledges", "unit_id", nullable=False)

    # 6) Covering index (org/unit + pledge_date)
    op.create_index(
        "ix_pledges_org_unit_pledge_date",
        "pledges",
        ["org_id", "unit_id", "pledge_date"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_pledges_org_unit_pledge_date", table_name="pledges")

    # Drop FKs
    op.drop_constraint("fk_pledges_unit", "pledges", type_="foreignkey")
    op.drop_constraint("fk_pledges_org", "pledges", type_="foreignkey")

    # Drop columns
    op.drop_column("pledges", "unit_id")
    op.drop_column("pledges", "org_id")
