"""Explicit candidate metadata: no broker availability or retail eligibility claim."""

import argparse
import hashlib
from pathlib import Path
from typing import Literal, Self
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.audit import append_event
from app.crypto_catalog import keep
from app.database import Database
from app.domain_types import InstrumentKind, InstrumentStatus, TradingMode, UtcTimestamp, utc_now
from app.models import AuditEvent, Instrument, InstrumentAlias, QuoteCurrency, Venue
from app.models.audit import AuditType
from app.settings import Settings, load_settings

MAX_BYTES = 200_000
VENUES = {"XETR": ("Xetra", "Europe/Berlin"), "XAMS": ("Euronext Amsterdam", "Europe/Amsterdam")}


class CandidateError(ValueError):
    """Invalid/conflicting candidate configuration; no catalog writes allowed."""


def candidate_id(mic: str, isin: str) -> UUID:
    return uuid5(NAMESPACE_URL, "https://trading-ai.invalid/security/" + mic + "/" + isin)


class Candidate(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.]{0,19}$")
    name: str = Field(min_length=1, max_length=160)
    isin: str = Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    mic: Literal["XETR", "XAMS"]
    quote_currency: Literal["EUR"]
    share_class_currency: Literal["EUR", "USD"]
    kind: Literal["STOCK", "UCITS_ETF"]
    issuer_ucits: bool
    broker_availability: Literal["UNKNOWN"]
    hr_retail_eligibility: Literal["UNKNOWN"]
    liquidity_status: Literal["UNVERIFIED"]
    source_urls: list[HttpUrl] = Field(min_length=1, max_length=4)

    @field_validator("isin")
    @classmethod
    def valid_isin(cls, value: str) -> str:
        digits = "".join(char if char.isdigit() else str(ord(char) - 55) for char in value)
        total = 0
        for position, char in enumerate(reversed(digits)):
            number = int(char) * (2 if position % 2 else 1)
            total += number // 10 + number % 10
        if total % 10:
            raise ValueError("invalid ISIN check digit")
        return value

    @field_validator("source_urls")
    @classmethod
    def https_sources(cls, value: list[HttpUrl]) -> list[HttpUrl]:
        if any(url.scheme != "https" or url.username or url.password for url in value):
            raise ValueError("public HTTPS source references required")
        return value

    @model_validator(mode="after")
    def product_class(self) -> Self:
        if self.issuer_ucits != (self.kind == "UCITS_ETF"):
            raise ValueError("issuer UCITS classification must match product kind")
        return self


class Universe(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    version: Literal[1]
    reviewed_at: UtcTimestamp
    candidates: list[Candidate]

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("integer version required")
        return value

    @model_validator(mode="after")
    def valid_universe(self) -> Self:
        stocks = sum(row.kind == "STOCK" for row in self.candidates)
        if not 10 <= stocks <= 20 or not 2 <= len(self.candidates) - stocks <= 3:
            raise ValueError("10-20 stocks and 2-3 UCITS candidates required")
        if self.reviewed_at > utc_now():
            raise ValueError("candidate review time cannot be in the future")
        keys = {(row.mic, row.isin) for row in self.candidates}
        tickers = {(row.mic, row.ticker) for row in self.candidates}
        if len(keys) != len(self.candidates) or len(tickers) != len(self.candidates):
            raise ValueError("duplicate listing identity or same-venue ticker collision")
        return self


def parse_candidates(raw: bytes) -> Universe:
    if len(raw) > MAX_BYTES:
        raise CandidateError("Candidate configuration exceeds size limit")
    try:
        return Universe.model_validate_json(raw)
    except ValidationError:
        raise CandidateError("Invalid candidate configuration; no catalog change") from None


def import_candidates(session: Session, raw: bytes, settings: Settings) -> list[UUID]:
    if settings.trading_mode is not TradingMode.PAPER:
        raise CandidateError("Only PAPER metadata import is implemented")
    universe = parse_candidates(raw)
    digest = hashlib.sha256(raw).hexdigest()
    session.execute(text("SELECT pg_advisory_xact_lock(270027)"))
    currency = session.scalar(select(QuoteCurrency).where(QuoteCurrency.code == "EUR"))
    if currency is None:
        currency = keep(
            session, QuoteCurrency, candidate_id("EUR", "currency"), code="EUR", display_scale=2
        )
    elif currency.display_scale != 2:
        raise CandidateError("Existing EUR definition conflicts")
    result = []
    for row in universe.candidates:
        venue_name, zone = VENUES[row.mic]
        venue = keep(
            session,
            Venue,
            candidate_id(row.mic, "venue"),
            code=row.mic,
            name=venue_name,
            timezone=zone,
        )
        key = candidate_id(row.mic, row.isin)
        instrument = keep(
            session,
            Instrument,
            key,
            venue_id=venue.id,
            quote_currency_id=currency.id,
            symbol=row.ticker,
            name=row.name,
            isin=row.isin,
            kind=InstrumentKind(row.kind),
            status=InstrumentStatus.SUSPENDED,
        )
        keep(
            session,
            InstrumentAlias,
            candidate_id(row.mic, row.isin + "/candidate"),
            instrument_id=key,
            venue_id=venue.id,
            provider="SECURITY_CANDIDATE",
            alias=row.ticker,
        )
        audit_id = candidate_id(row.mic, row.isin + "/audit/" + digest)
        if session.get(AuditEvent, audit_id) is None:
            append_event(
                session,
                event_type=AuditType.SYSTEM,
                correlation_id=candidate_id("source", digest),
                entity_id=instrument.id,
                event_id=audit_id,
            )
        result.append(key)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    settings = load_settings()
    with args.file.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    database = Database(settings)
    try:
        with database.transaction() as session:
            ids = import_candidates(session, raw, settings)
        print(
            f"Imported {len(ids)} suspended candidates; broker/HR eligibility UNKNOWN; "
            f"source SHA256 {hashlib.sha256(raw).hexdigest()}"
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
