"""Versioned keyset cursors; positions are not authorization credentials."""

import base64
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain_types import UtcTimestamp
from app.models.jobs import JobStatus


class Page[T](BaseModel):
    items: list[T]
    limit: int
    next_cursor: str | None
    has_more: bool


class PageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=1024, pattern=r"^[A-Za-z0-9_-]+$")


class JobCursor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    created_at: UtcTimestamp
    id: UUID
    status: JobStatus | None = None
    queue_name: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9:-]{0,99}$")

    def encode(self) -> str:
        return (
            base64.urlsafe_b64encode(self.model_dump_json().encode("utf-8"))
            .decode("ascii")
            .rstrip("=")
        )

    @classmethod
    def decode(cls, value: str) -> "JobCursor":
        if not 1 <= len(value) <= 1024:
            raise ValueError("invalid cursor length")
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        return cls.model_validate_json(raw)
