"""create expenses table

Revision ID: 1faf53abc3a0
Revises: c7a8e9d0f1b2
Create Date: 2025-08-08 13:22:02.279051
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1faf53abc3a0"
down_revision = "c7a8e9d0f1b2"
branch_labels = None
depends_on = None


def upgrade():
    # Main expenses table
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),

        # Optional FK to categories; assumes categories.id exists (Integer).
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Keep vendors simple for now (no vendors table yet)
        sa.Column("vendor_name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),

        # Status + payment info
        sa.Column(
            "status",
            sa.Enum("PENDING", "PAID", name="expense_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),

        # Align with upcoming transaction fields so we can mirror later
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("reference_no", sa.String(length=100), nullable=True),

        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])
    op.create_index("ix_expenses_category_id", "expenses", ["category_id"])
    op.create_index("ix_expenses_status", "expenses", ["status"])


def downgrade():
    op.drop_index("ix_expenses_status", table_name="expenses")
    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_table("expenses")
    # Clean up enum in Postgres
    op.execute("DROP TYPE IF EXISTS expense_status")
