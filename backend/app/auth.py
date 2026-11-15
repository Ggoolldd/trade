"""Opaque bearer sessions and durable login throttling; no JWT signing key required."""

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from pwdlib import PasswordHash
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.audit import append_event
from app.database import Database
from app.domain_types import utc_now
from app.models.audit import AuditReason, AuditType
from app.models.auth import AuthSession, LoginThrottle, User, UserRole

password_hasher = PasswordHash.recommended()
# A non-user dummy hash equalizes expensive verification for unknown usernames.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
SESSION_LIFETIME = timedelta(minutes=15)
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_ATTEMPTS = 5


class AuthenticationDenied(PermissionError):
    def __init__(self, status_code: int = 401) -> None:
        super().__init__("Authentication rejected")
        self.status_code = status_code


@dataclass(frozen=True)
class Identity:
    user_id: UUID
    username: str
    session_id: UUID
    role: UserRole


@dataclass(frozen=True)
class Token:
    access_token: SecretStr
    expires_at: datetime


def create_user(
    session: Session, *, username: str, password: SecretStr, enabled: bool = False
) -> User:
    normalized = username.casefold()
    if not re.fullmatch(r"[a-z0-9_.-]{3,64}", normalized):
        raise ValueError("invalid username")
    if not 15 <= len(password.get_secret_value()) <= 128:
        raise ValueError("password length must be 15 through 128 characters")
    user = User(
        username=normalized,
        password_hash=password_hasher.hash(password.get_secret_value()),
        enabled=enabled,
    )
    session.add(user)
    session.flush()
    return user


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, database: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self.database = database
        self.clock = clock

    def login(
        self, *, username: str, password: SecretStr, source: str, correlation_id: UUID
    ) -> Token:
        normalized = username.casefold()
        if (
            not re.fullmatch(r"[a-z0-9_.-]{3,64}", normalized)
            or len(password.get_secret_value()) > 128
        ):
            raise AuthenticationDenied()
        now = self.clock()
        rejection = 0
        issued: Token | None = None
        keys = sorted([digest("user:" + normalized), digest("source:" + source)])
        with self.database.transaction() as session:
            buckets = []
            for key in keys:
                session.execute(
                    insert(LoginThrottle)
                    .values(key=key, failures=0, window_started_at=now)
                    .on_conflict_do_nothing(index_elements=["key"])
                )
                bucket = session.scalars(
                    select(LoginThrottle).where(LoginThrottle.key == key).with_for_update()
                ).one()
                if now >= bucket.window_started_at + LOGIN_WINDOW:
                    bucket.failures, bucket.window_started_at = 0, now
                buckets.append(bucket)
            user = session.scalar(select(User).where(User.username == normalized))
            if any(bucket.failures >= LOGIN_ATTEMPTS for bucket in buckets):
                rejection = 429
            else:
                correct = password_hasher.verify(
                    password.get_secret_value(), user.password_hash if user else dummy_hash
                )
                if user is None or not user.enabled or not correct:
                    for bucket in buckets:
                        bucket.failures += 1
                    rejection = 401
                else:
                    for bucket in buckets:
                        bucket.failures = 0
                    raw = secrets.token_urlsafe(32)
                    expires = now + SESSION_LIFETIME
                    session.add(
                        AuthSession(
                            user_id=user.id,
                            token_hash=digest(raw),
                            expires_at=expires,
                            created_at=now,
                        )
                    )
                    issued = Token(SecretStr(raw), expires)
            append_event(
                session,
                event_type=AuditType.AUTHENTICATION,
                correlation_id=correlation_id,
                actor_id=user.id if user else None,
                reason=AuditReason.AUTH_FAILURE if rejection else AuditReason.USER_ACTION,
            )
        # Failed attempt counters and audit must commit before raising to HTTP.
        if rejection:
            raise AuthenticationDenied(rejection)
        assert issued is not None
        return issued

    def identify(self, token: SecretStr) -> Identity:
        raw = token.get_secret_value()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
            raise AuthenticationDenied()
        with self.database.transaction() as session:
            row = session.execute(
                select(AuthSession, User)
                .join(User)
                .where(
                    AuthSession.token_hash == digest(raw),
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > self.clock(),
                    User.enabled.is_(True),
                )
            ).one_or_none()
            if row is None:
                raise AuthenticationDenied()
            active, user = row
            return Identity(user.id, user.username, active.id, user.role)

    def logout(self, identity: Identity, correlation_id: UUID) -> None:
        with self.database.transaction() as session:
            active = session.get(AuthSession, identity.session_id, with_for_update=True)
            if active is None or active.user_id != identity.user_id:
                raise AuthenticationDenied()
            active.revoked_at = self.clock()
            append_event(
                session,
                event_type=AuditType.AUTHENTICATION,
                correlation_id=correlation_id,
                actor_id=identity.user_id,
                reason=AuditReason.USER_ACTION,
            )
