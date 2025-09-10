"""Merge heads: org_layer_foundation + employee_comp_history

Resolves multiple heads by merging:
- 4c95c4046b3e (employee comp history)
- b1a2c3d4e5f6 (Organization layer foundation)
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# --- Alembic identifiers ---
revision = "f7a1e2c3d4e6"
down_revision = ("4c95c4046b3e", "b1a2c3d4e5f6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge point; no schema changes required.
    pass


def downgrade() -> None:
    # Un-merge: not typically supported; leave as no-op.
    pass
