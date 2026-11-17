"""Import provenance, explicitly separate from licensed/canonical market data."""

from typing import Any

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.orm_types import EntityColumns


class HistoryImport(EntityColumns, Base):
    __tablename__ = "history_imports"
    __table_args__ = (
        UniqueConstraint("manifest_sha256"),
        CheckConstraint(
            "manifest_sha256 ~ '^[a-f0-9]{64}$' AND source_sha256 ~ '^[a-f0-9]{64}$'", name="hashes"
        ),
        CheckConstraint("row_count BETWEEN 1 AND 5000", name="row_count"),
        CheckConstraint(
            "(manifest->>'purpose') IS NOT DISTINCT FROM 'SYNTHETIC_TEST_ONLY'",
            name="synthetic_only",
        ),
    )
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
