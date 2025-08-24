from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "fb22fafa61a6"
down_revision = "77c6958025b9"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "sigma_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("process", sa.String(length=100), nullable=False),
        sa.Column("ctq", sa.String(length=100), nullable=True),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("opportunities_per_unit", sa.Integer(), nullable=False),
        sa.Column("defects", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sigma_logs_process", "sigma_logs", ["process"], unique=False)
    op.create_index("ix_sigma_logs_period_start", "sigma_logs", ["period_start"], unique=False)

def downgrade():
    op.drop_index("ix_sigma_logs_period_start", table_name="sigma_logs")
    op.drop_index("ix_sigma_logs_process", table_name="sigma_logs")
    op.drop_table("sigma_logs")
