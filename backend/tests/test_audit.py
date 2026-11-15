from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.audit import append_event, verify_chain
from app.database import Database
from app.models.audit import AuditEvent, AuditReason, AuditType

pytestmark = pytest.mark.integration


@pytest.fixture
def audit_role(database: Database) -> Iterator[str]:
    role = "tai_audit_" + uuid4().hex
    with database.engine.begin() as connection:
        connection.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"))
        connection.execute(text(f"GRANT USAGE ON SCHEMA trading, public TO {role}"))
        connection.execute(text(f"GRANT SELECT, INSERT ON trading.audit_events TO {role}"))
    try:
        yield role
    finally:
        with database.engine.begin() as connection:
            connection.execute(text(f"REVOKE ALL ON trading.audit_events FROM {role}"))
            connection.execute(text(f"REVOKE ALL ON SCHEMA trading, public FROM {role}"))
            connection.execute(text(f"DROP ROLE {role}"))


def read_events(database: Database) -> list[AuditEvent]:
    with database.transaction() as session:
        return list(session.scalars(select(AuditEvent).order_by(AuditEvent.sequence)))


def test_runtime_append_but_update_delete_truncate_denied(
    database: Database, audit_role: str
) -> None:
    with database.transaction() as session:
        session.execute(text(f"SET LOCAL ROLE {audit_role}"))
        row = append_event(session, event_type=AuditType.SYSTEM, correlation_id=uuid4())
        identity = row.id
        assert row.sequence > 0
        assert len(row.event_hash) == 64
    for statement in [
        "UPDATE trading.audit_events SET reason='RECOVERY' WHERE id=:id",
        "DELETE FROM trading.audit_events WHERE id=:id",
        "TRUNCATE trading.audit_events",
    ]:
        with pytest.raises(DBAPIError):
            with database.transaction() as session:
                session.execute(text(f"SET LOCAL ROLE {audit_role}"))
                session.execute(text(statement), {"id": identity})
    # Defense in depth: even the table owner's ordinary DML hits immutable triggers.
    with pytest.raises(DBAPIError):
        with database.transaction() as session:
            session.execute(text("DELETE FROM trading.audit_events WHERE id=:id"), {"id": identity})


def test_concurrent_appends_form_one_chain_and_checkpoint_detects_tampering(
    database: Database, audit_role: str
) -> None:
    before = len(read_events(database))

    def append(_: int) -> None:
        with database.transaction() as session:
            session.execute(text(f"SET LOCAL ROLE {audit_role}"))
            append_event(session, event_type=AuditType.SYSTEM, correlation_id=uuid4())

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append, range(12)))
    events = read_events(database)
    assert len(events) == before + 12
    checkpoint = events[-1].event_hash
    assert verify_chain(events, expected_head=checkpoint, expected_count=len(events))
    assert not verify_chain(events[:-1], expected_head=checkpoint, expected_count=len(events))
    events[-1].reason = AuditReason.RECOVERY
    assert not verify_chain(events, expected_head=checkpoint, expected_count=len(events))


def test_rollback_and_duplicate_event_do_not_break_chain(database: Database) -> None:
    identity = uuid4()
    with database.transaction() as session:
        append_event(
            session, event_type=AuditType.SYSTEM, correlation_id=uuid4(), event_id=identity
        )
    before = read_events(database)
    with pytest.raises(IntegrityError):
        with database.transaction() as session:
            append_event(
                session, event_type=AuditType.SYSTEM, correlation_id=uuid4(), event_id=identity
            )
    with pytest.raises(RuntimeError):
        with database.transaction() as session:
            append_event(session, event_type=AuditType.SYSTEM, correlation_id=uuid4())
            raise RuntimeError("rollback")
    with database.transaction() as session:
        append_event(session, event_type=AuditType.SYSTEM, correlation_id=uuid4())
    events = read_events(database)
    assert len(events) == len(before) + 1
    assert verify_chain(events, expected_head=events[-1].event_hash, expected_count=len(events))


def test_audit_rejects_arbitrary_secret_fields() -> None:
    with pytest.raises(TypeError):
        AuditEvent(event_type=AuditType.SYSTEM, correlation_id=uuid4(), api_key="synthetic-canary")
