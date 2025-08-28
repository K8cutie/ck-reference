"""payroll_base: Employees, Periods, Runs, Items, Payslips, Configs

- Mirrors project anchors:
  - UUID PKs via postgresql.UUID(as_uuid=True) + python default uuid.uuid4
  - JSONB columns for flexible snapshots/config
  - created_at with server_default=func.now()
"""

from __future__ import annotations
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# --- Alembic headers ---------------------------------------------------------
revision: str = "a7a3d2b18c01"
down_revision: str | None = "ca054ec32245"
branch_labels = None
depends_on = None

# --- Enumerations ------------------------------------------------------------
employee_pay_type = sa.Enum(
    "monthly", "daily", "hourly",
    name="employee_pay_type",
)
payroll_period_status = sa.Enum(
    "draft", "open", "closed",
    name="payroll_period_status",
)
payroll_run_status = sa.Enum(
    "draft", "computed", "posted",
    name="payroll_run_status",
)
payroll_item_kind = sa.Enum(
    "earning", "deduction", "tax", "employer_contrib",
    name="payroll_item_kind",
)

def upgrade() -> None:
    # Do NOT pre-create enums; SQLAlchemy will create them on first table use.

    # employees ---------------------------------------------------------------
    op.create_table(
        "employees",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pay_type", employee_pay_type, nullable=False),
        sa.Column("monthly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("daily_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("tax_status", sa.String(length=20), nullable=True),
        sa.Column("sss_no", sa.String(length=20), nullable=True),
        sa.Column("philhealth_no", sa.String(length=20), nullable=True),
        sa.Column("pagibig_no", sa.String(length=20), nullable=True),
        sa.Column("tin", sa.String(length=20), nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    op.create_index("ix_employees_code", "employees", ["code"], unique=True)

    # payroll_periods ---------------------------------------------------------
    op.create_table(
        "payroll_periods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column("period_key", sa.String(length=32), nullable=False, unique=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=False),
        sa.Column("status", payroll_period_status, nullable=False, server_default="draft"),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_payroll_periods_period_key", "payroll_periods", ["period_key"], unique=True)

    # payroll_runs ------------------------------------------------------------
    op.create_table(
        "payroll_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_periods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("run_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", payroll_run_status, nullable=False, server_default="draft"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_no", sa.String(length=64), nullable=True, unique=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    op.create_index("ix_payroll_runs_period_id", "payroll_runs", ["period_id"])

    # payroll_items -----------------------------------------------------------
    op.create_table(
        "payroll_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", payroll_item_kind, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("rate", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_payroll_items_run_id", "payroll_items", ["run_id"])
    op.create_index("ix_payroll_items_employee_id", "payroll_items", ["employee_id"])
    op.create_index("ix_payroll_items_code", "payroll_items", ["code"])

    # payslips ---------------------------------------------------------------
    op.create_table(
        "payslips",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("gross_pay", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("net_pay", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("snapshot_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reference_no", sa.String(length=64), nullable=True, unique=True),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    op.create_index("ix_payslips_run_id", "payslips", ["run_id"])
    op.create_index("ix_payslips_employee_id", "payslips", ["employee_id"])

    # payroll_configs ---------------------------------------------------------
    op.create_table(
        "payroll_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            default=uuid.uuid4,
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_json", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("effective_from", sa.Date(), nullable=False),
    )
    op.create_index("ix_payroll_configs_key", "payroll_configs", ["key"])
    op.create_unique_constraint(
        "uq_payroll_configs_key_eff",
        "payroll_configs",
        ["key", "effective_from"],
    )

def downgrade() -> None:
    op.drop_constraint("uq_payroll_configs_key_eff", "payroll_configs", type_="unique")
    op.drop_index("ix_payroll_configs_key", table_name="payroll_configs")
    op.drop_table("payroll_configs")

    op.drop_index("ix_payslips_employee_id", table_name="payslips")
    op.drop_index("ix_payslips_run_id", table_name="payslips")
    op.drop_table("payslips")

    op.drop_index("ix_payroll_items_code", table_name="payroll_items")
    op.drop_index("ix_payroll_items_employee_id", table_name="payroll_items")
    op.drop_index("ix_payroll_items_run_id", table_name="payroll_items")
    op.drop_table("payroll_items")

    op.drop_index("ix_payroll_runs_period_id", table_name="payroll_runs")
    op.drop_table("payroll_runs")

    op.drop_index("ix_payroll_periods_period_key", table_name="payroll_periods")
    op.drop_table("payroll_periods")

    op.drop_index("ix_employees_code", table_name="employees")
    op.drop_table("employees")

    # drop enums last (safe because the tables that reference them are gone)
    payroll_item_kind.drop(op.get_bind(), checkfirst=True)
    payroll_run_status.drop(op.get_bind(), checkfirst=True)
    payroll_period_status.drop(op.get_bind(), checkfirst=True)
    employee_pay_type.drop(op.get_bind(), checkfirst=True)
