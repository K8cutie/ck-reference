from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6f0d3a1c2b34"
down_revision = "fb22fafa61a6"  # previous sigma_logs migration
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sigma_defects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("process", sa.String(length=100), nullable=False),
        sa.Column("ctq", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_end", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("count >= 0", name="ck_sigma_defects_count_nonneg"),
    )
    op.create_index("ix_sigma_defects_process", "sigma_defects", ["process"], unique=False)
    op.create_index("ix_sigma_defects_period_start", "sigma_defects", ["period_start"], unique=False)
    op.create_index("ix_sigma_defects_ctq", "sigma_defects", ["ctq"], unique=False)


def downgrade():
    op.drop_index("ix_sigma_defects_ctq", table_name="sigma_defects")
    op.drop_index("ix_sigma_defects_period_start", table_name="sigma_defects")
    op.drop_index("ix_sigma_defects_process", table_name="sigma_defects")
    op.drop_table("sigma_defects")
