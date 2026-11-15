"""Versioned spot metadata rules."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_spot_rules"
down_revision: str | Sequence[str] | None = "0009_demo_cash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_rules",
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tick_size", sa.Numeric(38, 18), nullable=False),
        sa.Column("quantity_step", sa.Numeric(38, 18), nullable=False),
        sa.Column("min_quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("min_notional_eur", sa.Numeric(38, 18), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instrument_rules")),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["trading.instruments.id"],
            name=op.f("fk_instrument_rules_instrument_id_instruments"),
        ),
        sa.UniqueConstraint(
            "instrument_id", "source_sha256", name=op.f("uq_instrument_rules_instrument_id")
        ),
        sa.CheckConstraint(
            "tick_size > 0 AND quantity_step > 0 AND min_quantity > 0 AND min_notional_eur > 0",
            name=op.f("ck_instrument_rules_positive_rules"),
        ),
        sa.CheckConstraint(
            "source_sha256 ~ '^[a-f0-9]{64}$'", name=op.f("ck_instrument_rules_source_hash")
        ),
        schema="trading",
    )


def downgrade() -> None:
    op.drop_table("instrument_rules", schema="trading")
