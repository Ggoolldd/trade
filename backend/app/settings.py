"""Validated startup configuration. No broker credentials or LIVE unlock exist."""

import logging
import os
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError

logger = logging.getLogger(__name__)


class TradingMode(StrEnum):
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class FeedProvider(StrEnum):
    FIXTURE = "FIXTURE"
    KRAKEN_PUBLIC = "KRAKEN_PUBLIC"


class ConfigurationError(RuntimeError):
    """A sanitized startup error, safe to log without configuration values."""


def validate_service_url(value: SecretStr, *, database: bool) -> SecretStr:
    raw = value.get_secret_value()
    try:
        parsed = urlsplit(raw)
        allowed = {"postgresql+psycopg"} if database else {"redis", "rediss"}
        if (
            parsed.scheme not in allowed
            or not parsed.hostname
            or any(char.isspace() for char in raw)
            or parsed.query
            or parsed.fragment
            or parsed.path in {"", "/"}
            or "/" in parsed.path[1:]
            or (parsed.port is not None and not 1 <= parsed.port <= 65535)
        ):
            raise ValueError
        if database and not parsed.username:
            raise ValueError
        if not database and (not parsed.path[1:].isdigit() or not 0 <= int(parsed.path[1:]) <= 15):
            raise ValueError
    except ValueError:
        raise ValueError("invalid service URL") from None
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    trading_mode: TradingMode = TradingMode.PAPER
    database_url: SecretStr = SecretStr("postgresql+psycopg://trading@127.0.0.1:5432/trading_ai")
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    feed_provider: FeedProvider = FeedProvider.FIXTURE
    feed_max_age_seconds: int = Field(default=60, ge=1, le=3600)
    service_timeout_seconds: float = Field(default=5.0, gt=0, le=30, allow_inf_nan=False)

    @field_validator("trading_mode")
    @classmethod
    def paper_only(cls, value: TradingMode) -> TradingMode:
        if value is not TradingMode.PAPER:
            raise ValueError("only PAPER is implemented; SHADOW and LIVE are locked")
        return value

    @field_validator("database_url")
    @classmethod
    def database_dsn(cls, value: SecretStr) -> SecretStr:
        return validate_service_url(value, database=True)

    @field_validator("redis_url")
    @classmethod
    def redis_dsn(cls, value: SecretStr) -> SecretStr:
        return validate_service_url(value, database=False)


def load_settings() -> Settings:
    known = {f"TAI_{name.upper()}" for name in Settings.model_fields}
    unknown = sorted(
        name for name in os.environ if name.upper().startswith("TAI_") and name.upper() not in known
    )
    try:
        if unknown:
            raise ConfigurationError("Unknown TAI_ settings: " + ", ".join(unknown))
        return Settings()
    except (ValidationError, SettingsError, ConfigurationError):
        # Neither exception details nor raw env values may enter startup logs.
        logger.error("configuration_invalid; check TAI_ settings and .env")
        raise ConfigurationError("Invalid configuration; check TAI_ settings and .env") from None
