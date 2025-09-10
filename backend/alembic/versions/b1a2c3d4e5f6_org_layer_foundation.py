"""Organization layer foundation: organizations, org_units, memberships

Creates core multi-tenant scaffolding without touching existing GL tables yet.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# --- Alembic identifiers ---
revision = "b1a2c3d4e5f6"
# If this doesn't match your current head, replace with the output of: alembic current -v
down_revision = "ca054ec32245"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- organizations ---
    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=False)

    # --- org_units (e.g., Parishes/Chapels) ---
    op.create_table(
        "org_units",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("unit_type", sa.String(length=32), nullable=True),  # e.g., parish, chapel
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("TRUE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], ondelete="CASCADE", name="fk_org_units_org"
        ),
    )
    op.create_index("ix_org_units_org_name", "org_units", ["org_id", "name"], unique=False)
    # Unique code within an organization (NULLs allowed; enforce only when provided)
    op.create_index(
        "uq_org_units_org_code",
        "org_units",
        ["org_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )

    # --- memberships (principal ↔ org/unit ↔ role) ---
    op.create_table(
        "memberships",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # Principal fields kept generic to avoid coupling to a specific users table at this stage
        sa.Column(
            "principal_kind",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'user'"),
        ),
        sa.Column("principal_id", sa.String(length=128), nullable=False),
        # Scope
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_id", sa.BigInteger(), nullable=True),
        # Role at that scope
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], ondelete="CASCADE", name="fk_memberships_org"
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["org_units.id"], ondelete="CASCADE", name="fk_memberships_unit"
        ),
    )
    op.create_index(
        "ix_memberships_scope_principal",
        "memberships",
        ["org_id", "unit_id", "principal_id"],
        unique=False,
    )
    op.create_index(
        "uq_memberships_unique_role",
        "memberships",
        ["org_id", "unit_id", "principal_id", "role"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_memberships_unique_role", table_name="memberships")
    op.drop_index("ix_memberships_scope_principal", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("uq_org_units_org_code", table_name="org_units")
    op.drop_index("ix_org_units_org_name", table_name="org_units")
    op.drop_table("org_units")

    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_table("organizations")
