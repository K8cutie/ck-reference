"""category_gl_map: per-category default GL accounts

Revision ID: 3a1f2c9d7ab0
Revises: e80d3f8954e3
Create Date: 2025-08-22 00:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "3a1f2c9d7ab0"
down_revision = "e80d3f8954e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category_gl_map",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("debit_account_id", sa.Integer(), nullable=True),
        sa.Column("credit_account_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["debit_account_id"], ["gl_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["credit_account_id"], ["gl_accounts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("category_id", name="uq_category_gl_map_category_id"),
    )
    op.create_index("ix_category_gl_map_category_id", "category_gl_map", ["category_id"])
    op.create_index("ix_category_gl_map_debit_account_id", "category_gl_map", ["debit_account_id"])
    op.create_index("ix_category_gl_map_credit_account_id", "category_gl_map", ["credit_account_id"])


def downgrade() -> None:
    op.drop_index("ix_category_gl_map_credit_account_id", table_name="category_gl_map")
    op.drop_index("ix_category_gl_map_debit_account_id", table_name="category_gl_map")
    op.drop_index("ix_category_gl_map_category_id", table_name="category_gl_map")
    op.drop_table("category_gl_map")
