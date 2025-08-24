"""Add created_at to sacraments

Revision ID: c7a8e9d0f1b2
Revises: b1f3d2a4c5e6
Create Date: 2025-08-08 08:20:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c7a8e9d0f1b2"
down_revision = "b1f3d2a4c5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sacraments",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("sacraments", "created_at")
