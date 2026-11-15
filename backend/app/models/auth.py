"""Local user credentials and revocable opaque session identities."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.orm_types import EntityColumns, UtcDateTime


class UserRole(StrEnum):
    OWNER = "owner"
    READONLY = "readonly"
    SYSTEM_WORKER = "system_worker"


class User(EntityColumns, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username"),
        CheckConstraint("username ~ '^[a-z0-9_.-]{3,64}$'", name="username_format"),
        CheckConstraint("password_hash LIKE '$argon2id$%'", name="password_hash_format"),
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=UserRole.READONLY,
        server_default="readonly",
        nullable=False,
    )


class AuthSession(EntityColumns, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint("token_hash ~ '^[a-f0-9]{64}$'", name="token_hash_format"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("trading.users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class LoginThrottle(EntityColumns, Base):
    __tablename__ = "login_throttles"
    __table_args__ = (
        UniqueConstraint("key"),
        CheckConstraint("failures BETWEEN 0 AND 5", name="failure_count"),
        CheckConstraint("key ~ '^[a-f0-9]{64}$'", name="key_format"),
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(UtcDateTime(), nullable=False)
