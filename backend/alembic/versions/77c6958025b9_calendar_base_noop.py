from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "77c6958025b9"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # no-op: calendar tables already exist in DB
    pass

def downgrade():
    pass
