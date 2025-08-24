"""accounts, funds, pledges + tx columns

Revision ID: c785abfe37c0
Revises: 90f206605319
Create Date: 2025-08-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum  # 👈 use PG enum

# revision identifiers, used by Alembic.
revision = "c785abfe37c0"
down_revision = "90f206605319"
branch_labels = None
depends_on = None


def upgrade():
    # -- Create enums safely (no error if they already exist) -----------------
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'account_type') THEN
            CREATE TYPE account_type AS ENUM ('cash','bank','ewallet','other');
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pledge_status') THEN
            CREATE TYPE pledge_status AS ENUM ('ACTIVE','FULFILLED','CANCELLED');
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pledge_frequency') THEN
            CREATE TYPE pledge_frequency AS ENUM ('one_time','weekly','monthly','quarterly','annual');
          END IF;
        END $$;
        """
    )

    # --- accounts ------------------------------------------------------------
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "type",
            PGEnum("cash", "bank", "ewallet", "other", name="account_type", create_type=False),
            nullable=False,
        ),
        sa.Column("institution", sa.String(length=100), nullable=True),
        sa.Column("account_no", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="PHP"),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])

    # --- funds ---------------------------------------------------------------
    op.create_table(
        "funds",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("restricted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_funds_code_unique", "funds", ["code"], unique=True, postgresql_where=sa.text("code IS NOT NULL")
    )
    op.create_index("ix_funds_name", "funds", ["name"])

    # --- pledges -------------------------------------------------------------
    op.create_table(
        "pledges",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("parishioner_id", sa.Integer(), sa.ForeignKey("parishioners.id", ondelete="SET NULL"), nullable=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pledge_date", sa.Date(), nullable=False),
        sa.Column("amount_total", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "frequency",
            PGEnum("one_time", "weekly", "monthly", "quarterly", "annual", name="pledge_frequency", create_type=False),
            nullable=False,
            server_default="one_time",
        ),
        sa.Column(
            "status",
            PGEnum("ACTIVE", "FULFILLED", "CANCELLED", name="pledge_status", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pledges_fund_id", "pledges", ["fund_id"])
    op.create_index("ix_pledges_parishioner_id", "pledges", ["parishioner_id"])
    op.create_index("ix_pledges_status", "pledges", ["status"])

    # --- transactions extra columns -----------------------------------------
    op.add_column(
        "transactions",
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("pledge_id", sa.Integer(), sa.ForeignKey("pledges.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("transactions", sa.Column("transfer_ref", sa.String(length=100), nullable=True))
    op.add_column("transactions", sa.Column("batch_id", sa.String(length=100), nullable=True))
    op.add_column(
        "transactions", sa.Column("reconciled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE"))
    )
    op.add_column("transactions", sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_fund_id", "transactions", ["fund_id"])
    op.create_index("ix_transactions_pledge_id", "transactions", ["pledge_id"])
    op.create_index("ix_transactions_transfer_ref", "transactions", ["transfer_ref"])
    op.create_index("ix_transactions_batch_id", "transactions", ["batch_id"])
    op.create_index("ix_transactions_reconciled", "transactions", ["reconciled"])


def downgrade():
    # Drop indexes on transactions
    op.drop_index("ix_transactions_reconciled", table_name="transactions")
    op.drop_index("ix_transactions_batch_id", table_name="transactions")
    op.drop_index("ix_transactions_transfer_ref", table_name="transactions")
    op.drop_index("ix_transactions_pledge_id", table_name="transactions")
    op.drop_index("ix_transactions_fund_id", table_name="transactions")
    op.drop_index("ix_transactions_account_id", table_name="transactions")

    # Drop columns on transactions
    op.drop_column("transactions", "reconciled_at")
    op.drop_column("transactions", "reconciled")
    op.drop_column("transactions", "batch_id")
    op.drop_column("transactions", "transfer_ref")
    op.drop_column("transactions", "pledge_id")
    op.drop_column("transactions", "fund_id")
    op.drop_column("transactions", "account_id")

    # Drop pledges
    op.drop_index("ix_pledges_status", table_name="pledges")
    op.drop_index("ix_pledges_parishioner_id", table_name="pledges")
    op.drop_index("ix_pledges_fund_id", table_name="pledges")
    op.drop_table("pledges")

    # Drop funds
    op.drop_index("ix_funds_name", table_name="funds")
    op.drop_index("uq_funds_code_unique", table_name="funds")
    op.drop_table("funds")

    # Drop accounts
    op.drop_index("ix_accounts_name", table_name="accounts")
    op.drop_table("accounts")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS pledge_frequency")
    op.execute("DROP TYPE IF EXISTS pledge_status")
    op.execute("DROP TYPE IF EXISTS account_type")
