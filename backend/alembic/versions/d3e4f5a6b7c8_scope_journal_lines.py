"""Add org/unit scope to GL lines: journal_lines

- Adds org_id & unit_id with FKs
- Backfills from parent journal_entries
- Adds covering index for org/unit queries
"""

from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add nullable columns first
    op.add_column("journal_lines", sa.Column("org_id", sa.BigInteger(), nullable=True))
    op.add_column("journal_lines", sa.Column("unit_id", sa.BigInteger(), nullable=True))

    # 2) FKs
    op.create_foreign_key(
        "fk_journal_lines_org",
        "journal_lines",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_journal_lines_unit",
        "journal_lines",
        "org_units",
        ["unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3) Backfill from parent entries
    op.execute(
        """
        UPDATE journal_lines jl
        SET org_id = je.org_id,
            unit_id = je.unit_id
        FROM journal_entries je
        WHERE jl.entry_id = je.id
          AND (jl.org_id IS NULL OR jl.unit_id IS NULL);
        """
    )

    # 4) Tighten to NOT NULL
    op.alter_column("journal_lines", "org_id", nullable=False)
    op.alter_column("journal_lines", "unit_id", nullable=False)

    # 5) Covering index
    op.create_index(
        "ix_journal_lines_org_unit_entry_id",
        "journal_lines",
        ["org_id", "unit_id", "entry_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_journal_lines_org_unit_entry_id", table_name="journal_lines")

    # Drop FKs
    op.drop_constraint("fk_journal_lines_unit", "journal_lines", type_="foreignkey")
    op.drop_constraint("fk_journal_lines_org", "journal_lines", type_="foreignkey")

    # Drop columns
    op.drop_column("journal_lines", "unit_id")
    op.drop_column("journal_lines", "org_id")
