"""employee comp history

Revision ID: 4c95c4046b3e
Revises: 09efc858df61
Create Date: 2025-08-29 06:25:01.300647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4c95c4046b3e"
down_revision: Union[str, Sequence[str], None] = "09efc858df61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Track compensation changes (promotions, adjustments) per employee.
    op.create_table(
        "employee_comp_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=True),  # e.g., promotion, adjustment
        sa.Column("reason", sa.Text(), nullable=True),

        # Old/New pay types & rates (strings/numerics to avoid enum churn)
        sa.Column("old_pay_type", sa.String(length=20), nullable=True),
        sa.Column("new_pay_type", sa.String(length=20), nullable=True),
        sa.Column("old_monthly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_monthly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("old_daily_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_daily_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("old_hourly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_hourly_rate", sa.Numeric(12, 2), nullable=True),

        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_employee_comp_history_employee_id",
        "employee_comp_history",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_employee_comp_history_effective_date",
        "employee_comp_history",
        ["effective_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_employee_comp_history_effective_date", table_name="employee_comp_history")
    op.drop_index("ix_employee_comp_history_employee_id", table_name="employee_comp_history")
    op.drop_table("employee_comp_history")
