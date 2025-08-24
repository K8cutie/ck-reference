"""add payment_method and reference_no to transactions

Revision ID: 9824c42a3985
Revises: 5dafe923866a
Create Date: 2025-08-07 05:09:04.792226
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql  # ✅ required for ENUM creation

# revision identifiers, used by Alembic.
revision: str = '9824c42a3985'
down_revision: Union[str, Sequence[str], None] = '5dafe923866a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ✅ Explicitly create ENUM before adding column
    payment_method_enum = postgresql.ENUM('cash', 'gcash', 'check', 'bank', 'other', name='paymentmethod')
    payment_method_enum.create(op.get_bind())

    # ✅ Add both new columns
    op.add_column('transactions', sa.Column(
        'payment_method',
        sa.Enum('cash', 'gcash', 'check', 'bank', 'other', name='paymentmethod'),
        nullable=True
    ))
    op.add_column('transactions', sa.Column('reference_no', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # ✅ Drop the columns
    op.drop_column('transactions', 'reference_no')
    op.drop_column('transactions', 'payment_method')

    # ✅ Drop the ENUM type from DB
    payment_method_enum = postgresql.ENUM(name='paymentmethod')
    payment_method_enum.drop(op.get_bind())
