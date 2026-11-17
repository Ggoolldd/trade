"""Explicit synthetic historical import provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_history_imports"
down_revision: str | Sequence[str] | None = "0010_spot_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "history_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_history_imports")),
        sa.UniqueConstraint("manifest_sha256", name=op.f("uq_history_imports_manifest_sha256")),
        sa.CheckConstraint(
            "manifest_sha256 ~ '^[a-f0-9]{64}$' AND source_sha256 ~ '^[a-f0-9]{64}$'",
            name=op.f("ck_history_imports_hashes"),
        ),
        sa.CheckConstraint(
            "row_count BETWEEN 1 AND 5000", name=op.f("ck_history_imports_row_count")
        ),
        sa.CheckConstraint(
            "(manifest->>'purpose') IS NOT DISTINCT FROM 'SYNTHETIC_TEST_ONLY'",
            name=op.f("ck_history_imports_synthetic_only"),
        ),
        schema="trading",
    )


def downgrade() -> None:
    op.drop_table("history_imports", schema="trading")
