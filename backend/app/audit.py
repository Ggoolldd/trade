"""Append within the caller's transaction; verify against a trusted checkpoint."""

import hashlib
import hmac
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain_types import require_utc
from app.models.audit import AuditEvent, AuditReason, AuditType

GENESIS = "0" * 64


def append_event(
    session: Session,
    *,
    event_type: AuditType,
    correlation_id: UUID,
    reason: AuditReason = AuditReason.SYSTEM_EVENT,
    actor_id: UUID | None = None,
    entity_id: UUID | None = None,
    event_id: UUID | None = None,
) -> AuditEvent:
    values: dict[str, object] = dict(
        event_type=event_type,
        correlation_id=correlation_id,
        reason=reason,
        actor_id=actor_id,
        entity_id=entity_id,
    )
    if event_id is not None:
        values["id"] = event_id
    event = AuditEvent(**values)
    session.add(event)
    session.flush()
    return event


def verify_chain(events: Sequence[AuditEvent], *, expected_head: str, expected_count: int) -> bool:
    previous = GENESIS
    for position, event in enumerate(events, 1):
        canonical = "|".join(
            [
                str(event.sequence),
                str(event.id),
                event.event_type.value,
                event.reason.value,
                event.mode.value,
                str(event.correlation_id),
                str(event.actor_id or ""),
                str(event.entity_id or ""),
                require_utc(event.created_at).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            ]
        )
        digest = hashlib.sha256((previous + canonical).encode("utf-8")).hexdigest()
        if (
            event.sequence != position
            or not hmac.compare_digest(previous, event.previous_hash)
            or not hmac.compare_digest(digest, event.event_hash)
        ):
            return False
        previous = event.event_hash
    return len(events) == expected_count and hmac.compare_digest(previous, expected_head)
