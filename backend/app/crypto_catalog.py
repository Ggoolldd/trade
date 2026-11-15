"""Read-only Kraken public spot metadata; imported instruments stay suspended."""

import argparse
import hashlib
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Literal
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit import append_event
from app.database import Base, Database
from app.domain_types import (
    FinancialDecimal,
    InstrumentKind,
    InstrumentStatus,
    TradingMode,
    require_utc,
    utc_now,
)
from app.models import Instrument, InstrumentAlias, InstrumentRules, QuoteCurrency, Venue
from app.models.audit import AuditType
from app.settings import Settings, load_settings

PUBLIC_URL = "https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR,ETHEUR"
MAX_BYTES = 200_000
PAIRS = {
    "BTC/EUR": ("XXBTZEUR", "XBTEUR", "XBT/EUR", "XXBT"),
    "ETH/EUR": ("XETHZEUR", "ETHEUR", "ETH/EUR", "XETH"),
}


class CatalogError(ValueError):
    """Unsupported, unavailable or conflicting spot metadata; fail closed."""


class PairMetadata(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")
    altname: str
    wsname: str
    base: str
    quote: Literal["ZEUR"]
    aclass_base: Literal["currency"]
    aclass_quote: Literal["currency"]
    lot: Literal["unit"]
    lot_multiplier: int = Field(ge=1, le=1)
    lot_decimals: int = Field(ge=0, le=18)
    pair_decimals: int = Field(ge=0, le=18)
    tick_size: FinancialDecimal = Field(gt=0)
    ordermin: FinancialDecimal = Field(gt=0)
    costmin: FinancialDecimal = Field(gt=0)
    status: Literal["online"]

    @field_validator("lot_multiplier", "lot_decimals", "pair_decimals", mode="before")
    @classmethod
    def strict_integer(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("integer precision required")
        return value


class Response(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    error: list[str]
    result: dict[str, PairMetadata]


def catalog_id(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, "https://trading-ai.invalid/catalog/kraken/" + name)


def parse_pairs(raw: bytes) -> dict[str, PairMetadata]:
    if len(raw) > MAX_BYTES:
        raise CatalogError("Public metadata response exceeds size limit")
    try:
        response = Response.model_validate_json(raw)
        if response.error or set(response.result) != {row[0] for row in PAIRS.values()}:
            raise CatalogError("Expected exactly the two supported EUR spot pairs")
        canonical: dict[str, PairMetadata] = {}
        for symbol, (key, alternate, websocket, base) in PAIRS.items():
            row = response.result[key]
            if (row.altname, row.wsname, row.base) != (alternate, websocket, base):
                raise CatalogError("Conflicting pair identity")
            # Tick precision must be representable, without binary floats or rounding.
            with localcontext() as context:
                context.prec = 80
                if row.tick_size % Decimal(1).scaleb(-row.pair_decimals) != 0:
                    raise CatalogError("Tick conflicts with price precision")
                if row.ordermin % Decimal(1).scaleb(-row.lot_decimals) != 0:
                    raise CatalogError("Minimum quantity conflicts with lot precision")
            canonical[symbol] = row
        return canonical
    except ValidationError:
        raise CatalogError("Invalid or unavailable public spot metadata") from None


def resolve_pair(raw: bytes, symbol: str) -> PairMetadata:
    if symbol not in PAIRS:
        raise CatalogError("Unsupported canonical spot pair")
    return parse_pairs(raw)[symbol]


def fetch_public() -> bytes:
    try:
        request = Request(PUBLIC_URL, headers={"User-Agent": "TRADING-AI-public-catalog"})
        with urlopen(request, timeout=20) as response:
            raw = bytes(response.read(MAX_BYTES + 1))
    except (URLError, TimeoutError, OSError):
        raise CatalogError("Public metadata fetch failed; no catalog change") from None
    parse_pairs(raw)
    return raw


def keep[Model: Base](session: Session, model: type[Model], key: UUID, **fields: object) -> Model:
    existing = session.get(model, key)
    if existing is not None:
        if any(getattr(existing, name) != value for name, value in fields.items()):
            raise CatalogError("Existing catalog identity/rules conflict; refusing overwrite")
        return existing
    value = model(id=key, **fields)
    session.add(value)
    session.flush()
    return value


def import_pairs(
    session: Session, raw: bytes, observed_at: datetime, settings: Settings
) -> list[UUID]:
    if settings.trading_mode is not TradingMode.PAPER:
        raise CatalogError("Only PAPER catalog import is implemented")
    timestamp = require_utc(observed_at)
    if timestamp > utc_now():
        raise CatalogError("Metadata observation cannot be in the future")
    pairs = parse_pairs(raw)
    digest = hashlib.sha256(raw).hexdigest()
    session.execute(text("SELECT pg_advisory_xact_lock(260026)"))
    currency = session.scalar(select(QuoteCurrency).where(QuoteCurrency.code == "EUR"))
    if currency is None:
        currency = keep(session, QuoteCurrency, catalog_id("EUR"), code="EUR", display_scale=2)
    elif currency.display_scale != 2:
        raise CatalogError("Existing EUR definition conflicts")
    venue = keep(
        session, Venue, catalog_id("venue"), code="KRAKEN", name="Kraken spot", timezone="UTC"
    )
    result = []
    for symbol, pair in pairs.items():
        instrument = keep(
            session,
            Instrument,
            catalog_id(symbol),
            venue_id=venue.id,
            quote_currency_id=currency.id,
            symbol=symbol,
            name=symbol + " spot",
            kind=InstrumentKind.SPOT_CRYPTO,
            status=InstrumentStatus.SUSPENDED,
            isin=None,
        )
        for provider, alias in [
            ("KRAKEN_REST", PAIRS[symbol][0]),
            ("KRAKEN_REST", pair.altname),
            ("KRAKEN_WS", pair.wsname),
        ]:
            keep(
                session,
                InstrumentAlias,
                catalog_id(symbol + "/" + provider + "/" + alias),
                instrument_id=instrument.id,
                venue_id=venue.id,
                provider=provider,
                alias=alias,
            )
        key = catalog_id(symbol + "/rules/" + digest)
        existing = session.get(InstrumentRules, key)
        # Identical bytes reuse first observation; replay never invents a newer usable time.
        rules = keep(
            session,
            InstrumentRules,
            key,
            instrument_id=instrument.id,
            source_sha256=digest,
            observed_at=existing.observed_at if existing else timestamp,
            tick_size=pair.tick_size,
            quantity_step=Decimal(1).scaleb(-pair.lot_decimals),
            min_quantity=pair.ordermin,
            min_notional_eur=pair.costmin,
        )
        if existing is None:
            append_event(
                session,
                event_type=AuditType.SYSTEM,
                correlation_id=rules.id,
                entity_id=instrument.id,
                event_id=catalog_id(symbol + "/audit/" + digest),
            )
        result.append(instrument.id)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--public", action="store_true", help="Read fixed public Kraken endpoint; no keys"
    )
    source.add_argument("--file", type=Path, help="Offline captured metadata")
    parser.add_argument("--observed-at", type=datetime.fromisoformat)
    args = parser.parse_args()
    if args.file and args.observed_at is None:
        parser.error("offline files require actual --observed-at; do not substitute replay time")
    settings = load_settings()
    if args.file:
        with args.file.open("rb") as source_file:
            raw = source_file.read(MAX_BYTES + 1)
    else:
        raw = fetch_public()
    observed = args.observed_at if args.file else utc_now()
    database = Database(settings)
    try:
        with database.transaction() as session:
            ids = import_pairs(session, raw, observed, settings)
        print("Imported two public spot metadata identities; instruments remain SUSPENDED:", ids)
    finally:
        database.close()


if __name__ == "__main__":
    main()
