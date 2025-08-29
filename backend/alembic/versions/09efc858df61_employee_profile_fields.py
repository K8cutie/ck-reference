"""employee profile fields

Revision ID: 09efc858df61
Revises: a7a3d2b18c01
Create Date: 2025-08-29 04:36:33.509676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09efc858df61'
down_revision: Union[str, Sequence[str], None] = 'a7a3d2b18c01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add profile / contact / address / emergency fields to employees
    with op.batch_alter_table("employees") as batch:
        # Contact
        batch.add_column(sa.Column("contact_no", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("email", sa.String(length=255), nullable=True))

        # Address
        batch.add_column(sa.Column("address_line1", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("address_line2", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("barangay", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("province", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("postal_code", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("country", sa.String(length=64), nullable=True))  # e.g., "Philippines"

        # Emergency contact
        batch.add_column(sa.Column("emergency_contact_name", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("emergency_contact_no", sa.String(length=32), nullable=True))

        # Notes
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.drop_column("notes")
        batch.drop_column("emergency_contact_no")
        batch.drop_column("emergency_contact_name")

        batch.drop_column("country")
        batch.drop_column("postal_code")
        batch.drop_column("province")
        batch.drop_column("city")
        batch.drop_column("barangay")
        batch.drop_column("address_line2")
        batch.drop_column("address_line1")

        batch.drop_column("email")
        batch.drop_column("contact_no")
