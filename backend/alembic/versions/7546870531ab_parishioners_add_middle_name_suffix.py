"""parishioners: add middle_name & suffix (safe)

Revision ID: 7546870531ab
Revises: 0e8b1643fccc
Create Date: 2025-08-10 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "7546870531ab"
down_revision: Union[str, Sequence[str], None] = "0e8b1643fccc"
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return insp.has_table(name)
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        cols = {c["name"] for c in insp.get_columns(table_name)}
    except Exception:
        return False
    return column_name in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "parishioners"):
        # Table not present in this environment; skip safely.
        return

    if not _has_column(bind, "parishioners", "middle_name"):
        op.add_column(
            "parishioners",
            sa.Column("middle_name", sa.String(length=100), nullable=True),
        )

    if not _has_column(bind, "parishioners", "suffix"):
        op.add_column(
            "parishioners",
            sa.Column("suffix", sa.String(length=50), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "parishioners"):
        return

    if _has_column(bind, "parishioners", "suffix"):
        op.drop_column("parishioners", "suffix")

    if _has_column(bind, "parishioners", "middle_name"):
        op.drop_column("parishioners", "middle_name")
