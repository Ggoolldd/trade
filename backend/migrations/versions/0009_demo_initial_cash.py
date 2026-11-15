"""Add non-spendable PAPER scenario starting cash configuration."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_demo_cash"
down_revision: str | Sequence[str] | None = "0008_schedules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_accounts",
        sa.Column("initial_cash_eur", sa.Numeric(38, 18), server_default="0", nullable=False),
        schema="trading",
    )
    op.create_check_constraint(
        op.f("ck_paper_accounts_initial_cash_nonnegative"),
        "paper_accounts",
        "initial_cash_eur >= 0",
        schema="trading",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_paper_accounts_initial_cash_nonnegative"),
        "paper_accounts",
        schema="trading",
        type_="check",
    )
    op.drop_column("paper_accounts", "initial_cash_eur", schema="trading")
