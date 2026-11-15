import logging
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.main import create_app
from app.settings import ConfigurationError, FeedProvider, Settings, TradingMode, load_settings


def test_defaults_are_paper_and_offline() -> None:
    config = load_settings()
    assert config.trading_mode is TradingMode.PAPER
    assert config.feed_provider is FeedProvider.FIXTURE
    assert config.feed_max_age_seconds == 60
    assert create_app().state.settings == config


@pytest.mark.parametrize("value", ["LIVE", "SHADOW", "paper", "LIV", "", " PAPER "])
def test_invalid_or_unimplemented_modes_fail_before_app_creation(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TAI_TRADING_MODE", value)
    with pytest.raises(ConfigurationError):
        create_app()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("TAI_DATABASE_URL", "sqlite:///local.db"),
        ("TAI_DATABASE_URL", "postgresql+psycopg://host/db"),
        ("TAI_DATABASE_URL", "postgresql+psycopg://user@host/"),
        ("TAI_DATABASE_URL", "postgresql+psycopg://user@host:99999/db"),
        ("TAI_DATABASE_URL", "postgresql+psycopg://user@host:abc/db"),
        ("TAI_DATABASE_URL", "postgresql+psycopg://user@bad host/db"),
        ("TAI_REDIS_URL", "http://host/0"),
        ("TAI_REDIS_URL", "redis://host/nope"),
        ("TAI_REDIS_URL", "redis://host/16"),
        ("TAI_REDIS_URL", "redis://host/0?password=bad"),
        ("TAI_FEED_PROVIDER", "PRIVATE_BROKER"),
        ("TAI_FEED_MAX_AGE_SECONDS", "0"),
        ("TAI_FEED_MAX_AGE_SECONDS", "3601"),
        ("TAI_SERVICE_TIMEOUT_SECONDS", "NaN"),
        ("TAI_SERVICE_TIMEOUT_SECONDS", "inf"),
        ("TAI_SERVICE_TIMEOUT_SECONDS", "-1"),
        ("TAI_TRADNG_MODE", "PAPER"),
        ("TAI_LIVE_UNLOCK", "true"),
    ],
)
def test_bad_env_fails_closed(monkeypatch: pytest.MonkeyPatch, key: str, value: str) -> None:
    monkeypatch.setenv(key, value)
    with pytest.raises(ConfigurationError):
        load_settings()


def test_env_overrides_dotenv_and_valid_service_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Path(".env").write_text("TAI_FEED_MAX_AGE_SECONDS=15\n", encoding="utf-8")
    monkeypatch.setenv("TAI_FEED_MAX_AGE_SECONDS", "30")
    monkeypatch.setenv("TAI_DATABASE_URL", "postgresql+psycopg://test:placeholder@db:5432/paper")
    monkeypatch.setenv("TAI_REDIS_URL", "rediss://:placeholder@cache:6380/1")
    monkeypatch.setenv("TAI_FEED_PROVIDER", "KRAKEN_PUBLIC")
    config = load_settings()
    assert config.feed_max_age_seconds == 30
    assert config.feed_provider is FeedProvider.KRAKEN_PUBLIC
    assert "placeholder" not in repr(config)
    assert "placeholder" not in config.model_dump_json()


def test_dotenv_unknown_and_invalid_mode_rejected() -> None:
    for contents in ["TAI_TRADING_MODE=LIVE\n", "TAI_TYPO=yes\n"]:
        Path(".env").write_text(contents, encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_settings()


def test_validation_errors_and_logs_do_not_leak_dsn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    marker = "synthetic-sensitive-canary"
    monkeypatch.setenv("TAI_DATABASE_URL", f"wrong://user:{marker}@host/db")
    caplog.set_level(logging.ERROR)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert marker not in str(caught.value)
    assert marker not in caplog.text
    with pytest.raises(ValidationError) as raw:
        Settings(database_url=SecretStr(f"wrong://user:{marker}@host/db"))
    assert marker not in str(raw.value)


def test_settings_cannot_change_mode_after_validation() -> None:
    config = load_settings()
    with pytest.raises(ValidationError):
        config.trading_mode = TradingMode.LIVE
