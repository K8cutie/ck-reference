"""accounting_core_books_only

Revision ID: e80d3f8954e3
Revises: 7546870531ab
Create Date: 2025-08-14 16:43:41.801010
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e80d3f8954e3"
down_revision: Union[str, Sequence[str], None] = "7546870531ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums: create if missing (idempotent)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gl_account_type') THEN
                CREATE TYPE gl_account_type AS ENUM ('asset','liability','equity','income','expense');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gl_normal_side') THEN
                CREATE TYPE gl_normal_side AS ENUM ('debit','credit');
            END IF;
        END$$;
        """
    )

    # --- Sequence for JE numbering
    op.execute("CREATE SEQUENCE IF NOT EXISTS je_entry_no_seq")

    # --- GL Accounts (Chart of Accounts)
    op.create_table(
        "gl_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "asset",
                "liability",
                "equity",
                "income",
                "expense",
                name="gl_account_type",
                create_type=False,   # <-- critical: don't recreate the type
            ),
            nullable=False,
        ),
        sa.Column(
            "normal_side",
            postgresql.ENUM(
                "debit",
                "credit",
                name="gl_normal_side",
                create_type=False,   # <-- critical: don't recreate the type
            ),
            nullable=False,
        ),
        sa.Column("is_cash", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_gl_accounts_code", "gl_accounts", ["code"])
    op.create_index("ix_gl_accounts_type", "gl_accounts", ["type"])
    op.create_index("ix_gl_accounts_is_cash", "gl_accounts", ["is_cash"])

    # --- Journal Entries (header)
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_no", sa.BigInteger(), nullable=False, server_default=sa.text("nextval('je_entry_no_seq')")),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(length=512), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False, server_default="PHP"),
        # Linkage to operational source
        sa.Column("reference_no", sa.String(length=64), nullable=True),
        sa.Column("source_module", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        # Posting/locking for audit trail
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("posted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_journal_entries_entry_no", "journal_entries", ["entry_no"])
    op.create_index("ix_journal_entries_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_refno", "journal_entries", ["reference_no"])
    op.create_index("ix_journal_entries_source", "journal_entries", ["source_module", "source_id"])

    # --- Journal Lines (detail)
    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "(debit >= 0 AND credit >= 0) AND ((debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0))",
            name="ck_journal_lines_one_side_positive",
        ),
    )
    op.create_index("ix_journal_lines_entry", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account", "journal_lines", ["account_id"])

    # --- Audit Logs (lightweight)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),  # e.g., 'journal_entry'
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),      # 'create','post','void','reprint'
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),                 # JSON (as text) for portability
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # --- Views for BIR Books (Books-Only mode)
    # General Journal
    op.execute("""
        CREATE OR REPLACE VIEW vw_general_journal AS
        SELECT
            je.entry_date::date AS date,
            je.entry_no,
            COALESCE(je.reference_no, CAST(je.entry_no AS text)) AS reference,
            COALESCE(jl.description, je.memo) AS description,
            ga.code AS account_code,
            ga.name AS account_title,
            jl.debit, jl.credit
        FROM journal_lines jl
        JOIN journal_entries je ON je.id = jl.entry_id
        JOIN gl_accounts ga ON ga.id = jl.account_id
        ORDER BY je.entry_date, je.entry_no, jl.line_no, jl.id;
    """)

    # General Ledger (with running balance per account)
    op.execute("""
        CREATE OR REPLACE VIEW vw_general_ledger AS
        SELECT
            ga.code AS account_code,
            ga.name AS account_title,
            je.entry_date::date AS date,
            COALESCE(jl.description, je.memo) AS description,
            COALESCE(je.reference_no, CAST(je.entry_no AS text)) AS reference,
            jl.debit, jl.credit,
            SUM(jl.debit - jl.credit) OVER (
                PARTITION BY ga.id
                ORDER BY je.entry_date, je.entry_no, jl.line_no, jl.id
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS running_balance
        FROM journal_lines jl
        JOIN journal_entries je ON je.id = jl.entry_id
        JOIN gl_accounts ga ON ga.id = jl.account_id
        ORDER BY ga.code, je.entry_date, je.entry_no, jl.line_no, jl.id;
    """)

    # Cash Receipts Book: entries that DEBIT a cash GL account
    op.execute("""
        CREATE OR REPLACE VIEW vw_cash_receipts_book AS
        WITH cash_debits AS (
            SELECT jl.entry_id, SUM(jl.debit) AS cash_amount
            FROM journal_lines jl
            JOIN gl_accounts ga ON ga.id = jl.account_id
            WHERE ga.is_cash = TRUE AND jl.debit > 0
            GROUP BY jl.entry_id
        ),
        other_credits AS (
            SELECT jl.entry_id,
                   string_agg(ga.name || ' ' || TO_CHAR(jl.credit, 'FM999,999,990.00'), ', ') AS credit_accounts
            FROM journal_lines jl
            JOIN gl_accounts ga ON ga.id = jl.account_id
            WHERE jl.credit > 0
            GROUP BY jl.entry_id
        )
        SELECT
            je.entry_date::date AS date,
            COALESCE(je.reference_no, CAST(je.entry_no AS text)) AS reference,
            je.memo AS description,
            oc.credit_accounts,
            cd.cash_amount AS amount_received
        FROM cash_debits cd
        JOIN journal_entries je ON je.id = cd.entry_id
        LEFT JOIN other_credits oc ON oc.entry_id = je.id
        ORDER BY je.entry_date, je.entry_no;
    """)

    # Cash Disbursements Book: entries that CREDIT a cash GL account
    op.execute("""
        CREATE OR REPLACE VIEW vw_cash_disbursements_book AS
        WITH cash_credits AS (
            SELECT jl.entry_id, SUM(jl.credit) AS cash_amount
            FROM journal_lines jl
            JOIN gl_accounts ga ON ga.id = jl.account_id
            WHERE ga.is_cash = TRUE AND jl.credit > 0
            GROUP BY jl.entry_id
        ),
        other_debits AS (
            SELECT jl.entry_id,
                   string_agg(ga.name || ' ' || TO_CHAR(jl.debit, 'FM999,999,990.00'), ', ') AS debit_accounts
            FROM journal_lines jl
            JOIN gl_accounts ga ON ga.id = jl.account_id
            WHERE jl.debit > 0
            GROUP BY jl.entry_id
        )
        SELECT
            je.entry_date::date AS date,
            COALESCE(je.reference_no, CAST(je.entry_no AS text)) AS reference,
            je.memo AS description,
            od.debit_accounts,
            cc.cash_amount AS amount_disbursed
        FROM cash_credits cc
        JOIN journal_entries je ON je.id = cc.entry_id
        LEFT JOIN other_debits od ON od.entry_id = je.id
        ORDER BY je.entry_date, je.entry_no;
    """)


def downgrade() -> None:
    # Drop views first
    op.execute("DROP VIEW IF EXISTS vw_cash_disbursements_book")
    op.execute("DROP VIEW IF EXISTS vw_cash_receipts_book")
    op.execute("DROP VIEW IF EXISTS vw_general_ledger")
    op.execute("DROP VIEW IF EXISTS vw_general_journal")

    # Drop tables
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_journal_lines_account", table_name="journal_lines")
    op.drop_index("ix_journal_lines_entry", table_name="journal_lines")
    op.drop_table("journal_lines")

    op.drop_constraint("uq_journal_entries_entry_no", "journal_entries", type_="unique")
    op.drop_index("ix_journal_entries_source", table_name="journal_entries")
    op.drop_index("ix_journal_entries_refno", table_name="journal_entries")
    op.drop_index("ix_journal_entries_date", table_name="journal_entries")
    op.drop_table("journal_entries")

    op.drop_index("ix_gl_accounts_is_cash", table_name="gl_accounts")
    op.drop_index("ix_gl_accounts_type", table_name="gl_accounts")
    op.drop_index("ix_gl_accounts_code", table_name="gl_accounts")
    op.drop_table("gl_accounts")

    # Drop sequence & enums
    op.execute("DROP SEQUENCE IF EXISTS je_entry_no_seq")
    op.execute("DROP TYPE IF EXISTS gl_account_type")
    op.execute("DROP TYPE IF EXISTS gl_normal_side")
