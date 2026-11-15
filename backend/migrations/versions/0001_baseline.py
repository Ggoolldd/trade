"""Initial namespace for domain tables; no synthetic financial data."""

from alembic import op
from sqlalchemy.schema import CreateSchema, DropSchema

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(CreateSchema("trading"))


def downgrade() -> None:
    # No CASCADE: unexpected remaining objects must fail rather than disappear.
    op.execute(DropSchema("trading"))
