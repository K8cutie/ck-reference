"""Add org/unit scope to payslips

- Adds org_id & unit_id with FKs
- Backfills from employees (by employee_id)
- Adds covering index for org-level queries
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("payslips", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("payslips", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_payslips_org",
        "payslips",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_payslips_unit",
        "payslips",
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

    # 4) Backfill from employees by employee_id
    op.execute(
        """
        UPDATE payslips p
        SET org_id = e.org_id,
            unit_id = e.unit_id
        FROM employees e
        WHERE p.employee_id = e.id
          AND (p.org_id IS NULL OR p.unit_id IS NULL);
        """
    )

    # 5) Any remaining NULLs → default scope (safety for legacy rows without employee match)
    op.execute(
        """
        WITH d AS (
            SELECT o.id AS org_id, u.id AS unit_id
            FROM organizations o
            JOIN org_units u ON u.org_id = o.id
            WHERE o.code = 'DIO-DEFAULT' AND u.code = 'PAR-DEFAULT'
            LIMIT 1
        )
        UPDATE payslips p
        SET org_id = COALESCE(p.org_id, d.org_id),
            unit_id = COALESCE(p.unit_id, d.unit_id)
        FROM d
        WHERE p.org_id IS NULL OR p.unit_id IS NULL;
        """
    )

    # 6) Tighten to NOT NULL
    op.alter_column("payslips", "org_id", nullable=False)
    op.alter_column("payslips", "unit_id", nullable=False)

    # 7) Covering index
    op.create_index(
        "ix_payslips_org_unit_created_at",
        "payslips",
        ["org_id", "unit_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_payslips_org_unit_created_at", table_name="payslips")

    # Drop FKs
    op.drop_constraint("fk_payslips_unit", "payslips", type_="foreignkey")
    op.drop_constraint("fk_payslips_org", "payslips", type_="foreignkey")

    # Drop columns
    op.drop_column("payslips", "unit_id")
    op.drop_column("payslips", "org_id")
