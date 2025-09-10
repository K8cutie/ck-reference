"""Add org/unit scope to categories

- Adds org_id (NOT NULL) & unit_id (nullable) with FKs
- Backfills existing rows to 'DIO-DEFAULT' / 'PAR-DEFAULT'
- Adds covering index for org/unit lookups
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "f6a7b8c9d0e1"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("categories", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("categories", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_categories_org",
        "categories",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_categories_unit",
        "categories",
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
        UPDATE categories c
        SET org_id = d.org_id,
            unit_id = COALESCE(c.unit_id, d.unit_id)
        FROM d
        WHERE c.org_id IS NULL;
        """
    )

    # 5) Tighten org_id to NOT NULL (unit_id stays nullable to allow org-wide categories later)
    op.alter_column("categories", "org_id", nullable=False)

    # 6) Covering index
    op.create_index(
        "ix_categories_org_unit_name",
        "categories",
        ["org_id", "unit_id", "name"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_categories_org_unit_name", table_name="categories")

    # Drop FKs
    op.drop_constraint("fk_categories_unit", "categories", type_="foreignkey")
    op.drop_constraint("fk_categories_org", "categories", type_="foreignkey")

    # Drop columns
    op.drop_column("categories", "unit_id")
    op.drop_column("categories", "org_id")
