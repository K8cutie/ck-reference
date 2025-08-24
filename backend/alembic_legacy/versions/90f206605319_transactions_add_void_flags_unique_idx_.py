"""transactions: add void flags + unique idx on (type, reference_no)

Revision ID: 90f206605319
Revises: 1faf53abc3a0
Create Date: 2025-08-08 14:05:22.631742
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90f206605319"
down_revision: Union[str, Sequence[str], None] = "1faf53abc3a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add void flags/metadata
    op.add_column(
        "transactions",
        sa.Column("voided", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "transactions",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("void_reason", sa.String(length=255), nullable=True),
    )

    # 2) Unique index for active (non-voided) refs only
    #    Allows duplicate refs across time as long as older ones are voided
    op.create_index(
        "uq_transactions_type_ref_not_void",
        "transactions",
        ["type", "reference_no"],
        unique=True,
        postgresql_where=sa.text("reference_no IS NOT NULL AND NOT voided"),
    )


def downgrade() -> None:
    op.drop_index("uq_transactions_type_ref_not_void", table_name="transactions")
    op.drop_column("transactions", "void_reason")
    op.drop_column("transactions", "voided_at")
    op.drop_column("transactions", "voided")
