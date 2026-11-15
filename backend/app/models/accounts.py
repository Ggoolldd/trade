"""Virtual account identities; production and broker identities are not accepted."""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.domain_types import TradingMode
from app.orm_types import EntityColumns


class DevelopmentEnvironment(StrEnum):
    LOCAL = "LOCAL"
    STAGING = "STAGING"


class AccountScope(StrEnum):
    READ = "READ"
    PAPER_TRADE = "PAPER_TRADE"
    POLICY_EDIT = "POLICY_EDIT"


class PaperAccount(EntityColumns, Base):
    __tablename__ = "paper_accounts"
    __table_args__ = (
        UniqueConstraint("environment", "name"),
        UniqueConstraint("id", "environment", name="uq_paper_accounts_identity_environment"),
        CheckConstraint("account_mode = 'PAPER'", name="paper_only"),
        CheckConstraint("length(btrim(name)) > 0", name="name_required"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_mode: Mapped[TradingMode] = mapped_column(
        Enum(
            TradingMode,
            name="account_mode",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=TradingMode.PAPER,
        nullable=False,
    )
    environment: Mapped[DevelopmentEnvironment] = mapped_column(
        Enum(
            DevelopmentEnvironment,
            name="development_environment",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TradingProfile(EntityColumns, Base):
    __tablename__ = "trading_profiles"
    __table_args__ = (
        UniqueConstraint("account_id", "name"),
        ForeignKeyConstraint(
            ["account_id", "environment"],
            ["trading.paper_accounts.id", "trading.paper_accounts.environment"],
            name="fk_profiles_account_environment",
        ),
        CheckConstraint("length(btrim(name)) > 0", name="name_required"),
    )
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    environment: Mapped[DevelopmentEnvironment] = mapped_column(
        Enum(
            DevelopmentEnvironment,
            name="profile_environment",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AccountPermission(EntityColumns, Base):
    __tablename__ = "account_permissions"
    __table_args__ = (
        UniqueConstraint("account_id", "principal_id", "scope"),
        ForeignKeyConstraint(
            ["account_id", "environment"],
            ["trading.paper_accounts.id", "trading.paper_accounts.environment"],
            name="fk_permissions_account_environment",
        ),
    )
    account_id: Mapped[UUID] = mapped_column(nullable=False)
    environment: Mapped[DevelopmentEnvironment] = mapped_column(
        Enum(
            DevelopmentEnvironment,
            name="permission_environment",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    principal_id: Mapped[UUID] = mapped_column(nullable=False)
    scope: Mapped[AccountScope] = mapped_column(
        Enum(
            AccountScope,
            name="account_scope",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
