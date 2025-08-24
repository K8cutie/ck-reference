"""ops: unique indexes for SAC refs (safe)

Revision ID: 0e8b1643fccc
Revises: 9d2f1ab3c7a4
Create Date: 2025-08-11 15:29:09.180658
"""
from typing import Sequence, Union, List, Optional
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0e8b1643fccc"
down_revision: Union[str, Sequence[str], None] = "9d2f1ab3c7a4"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return insp.has_table(name)
    except Exception:
        return False


def _has_columns(bind, table_name: str, cols: List[str]) -> bool:
    insp = sa.inspect(bind)
    try:
        existing = {c["name"] for c in insp.get_columns(table_name)}
    except Exception:
        return False
    return all(col in existing for col in cols)


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return index_name in {ix["name"] for ix in insp.get_indexes(table_name)}
    except Exception:
        return False


def safe_create_index(
    index_name: str,
    table_name: str,
    columns: List[str],
    unique: bool = True,
    postgresql_where: Optional[sa.sql.elements.TextClause] = None,
) -> None:
    bind = op.get_bind()
    if not _has_table(bind, table_name):
        return
    if not _has_columns(bind, table_name, columns):
        return
    if _index_exists(bind, table_name, index_name):
        return
    op.create_index(
        index_name,
        table_name,
        columns,
        unique=unique,
        postgresql_where=postgresql_where,
    )


def safe_drop_index(index_name: str, table_name: str) -> None:
    bind = op.get_bind()
    if not _has_table(bind, table_name):
        return
    if not _index_exists(bind, table_name, index_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    # Ensure sacraments↔transaction linkage is one-to-one via reference_no like "SAC-{id}"
    safe_create_index(
        "ux_transactions_reference_no",
        "transactions",
        ["reference_no"],
        unique=True,
    )

    # Only one active calendar event per external_ref; allow historical duplicates when inactive
    safe_create_index(
        "ux_calendar_external_ref",
        "calendar_events",
        ["external_ref"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    safe_drop_index("ux_calendar_external_ref", "calendar_events")
    safe_drop_index("ux_transactions_reference_no", "transactions")
