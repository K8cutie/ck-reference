"""add details jsonb to sacraments

Revision ID: 88a6d17ecac8
Revises: 6c09fc1e52b3
Create Date: 2025-08-07 10:03:49.340230
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "88a6d17ecac8"
down_revision: Union[str, Sequence[str], None] = "6c09fc1e52b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add non-null JSONB column with '{}' default."""
    op.add_column(
        "sacraments",
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema: drop the column."""
    op.drop_column("sacraments", "details")
