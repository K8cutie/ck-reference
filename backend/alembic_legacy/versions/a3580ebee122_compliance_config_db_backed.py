"""compliance config (db-backed)

Revision ID: a3580ebee122
Revises: c785abfe37c0
Create Date: 2025-08-09
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3580ebee122"
down_revision: Union[str, Sequence[str], None] = "c785abfe37c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enforce_voids", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("allow_hard_delete", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default=sa.text("3650")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "compliance_config_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("enforce_voids", sa.Boolean(), nullable=False),
        sa.Column("allow_hard_delete", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
    )

    # Seed a single row (id=1) with safe defaults
    op.execute(
        "INSERT INTO compliance_config (id, enforce_voids, allow_hard_delete, retention_days) "
        "VALUES (1, TRUE, FALSE, 3650)"
    )


def downgrade() -> None:
    op.drop_table("compliance_config_audit")
    op.drop_table("compliance_config")
