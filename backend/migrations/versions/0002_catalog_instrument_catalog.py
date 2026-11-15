"""instrument catalog

Revision ID: 0002_catalog
Revises: 0001_baseline
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_catalog"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed table ordering, constraints and explicit public version namespace.
    op.create_table(
        "quote_currencies",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("display_scale", sa.SmallInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9]{2,9}$'", name=op.f("ck_quote_currencies_code_format")
        ),
        sa.CheckConstraint(
            "display_scale BETWEEN 0 AND 18", name=op.f("ck_quote_currencies_scale_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quote_currencies")),
        sa.UniqueConstraint("code", name=op.f("uq_quote_currencies_code")),
        schema="trading",
    )
    op.create_table(
        "venues",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("code ~ '^[A-Z0-9_]{2,20}$'", name=op.f("ck_venues_code_format")),
        sa.CheckConstraint(
            "length(name) > 0 AND length(timezone) > 0", name=op.f("ck_venues_required_text")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_venues")),
        sa.UniqueConstraint("code", name=op.f("uq_venues_code")),
        schema="trading",
    )
    op.create_table(
        "instruments",
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("quote_currency_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "STOCK",
                "UCITS_ETF",
                "SPOT_CRYPTO",
                name="instrument_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "SUSPENDED",
                "DELISTED",
                name="instrument_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "isin IS NULL OR isin ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$'",
            name=op.f("ck_instruments_isin_format"),
        ),
        sa.CheckConstraint(
            "length(symbol) > 0 AND length(name) > 0", name=op.f("ck_instruments_required_text")
        ),
        sa.ForeignKeyConstraint(
            ["quote_currency_id"],
            ["trading.quote_currencies.id"],
            name=op.f("fk_instruments_quote_currency_id_quote_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["trading.venues.id"], name=op.f("fk_instruments_venue_id_venues")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
        sa.UniqueConstraint("id", "venue_id", name="uq_instruments_identity_venue"),
        sa.UniqueConstraint("venue_id", "symbol", name=op.f("uq_instruments_venue_id")),
        schema="trading",
    )
    op.create_table(
        "trading_hours",
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("closes_next_day", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(NOT closes_next_day AND closes_at > opens_at) OR "
            "(closes_next_day AND closes_at <= opens_at)",
            name=op.f("ck_trading_hours_session_interval"),
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_trading_hours_weekday_range")),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["trading.venues.id"], name=op.f("fk_trading_hours_venue_id_venues")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trading_hours")),
        sa.UniqueConstraint(
            "venue_id", "weekday", "opens_at", name=op.f("uq_trading_hours_venue_id")
        ),
        schema="trading",
    )
    op.create_table(
        "instrument_aliases",
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("alias", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(provider) > 0 AND length(alias) > 0",
            name=op.f("ck_instrument_aliases_required_text"),
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id", "venue_id"],
            ["trading.instruments.id", "trading.instruments.venue_id"],
            name="fk_instrument_alias_identity_venue",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instrument_aliases")),
        sa.UniqueConstraint(
            "venue_id", "provider", "alias", name=op.f("uq_instrument_aliases_venue_id")
        ),
        schema="trading",
    )


def downgrade() -> None:
    # Reviewed table ordering, constraints and explicit public version namespace.
    op.drop_table("instrument_aliases", schema="trading")
    op.drop_table("trading_hours", schema="trading")
    op.drop_table("instruments", schema="trading")
    op.drop_table("venues", schema="trading")
    op.drop_table("quote_currencies", schema="trading")
