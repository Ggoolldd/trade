import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import append_event
from app.database import Database
from app.domain_types import utc_now
from app.job_queue import JobQueue, enqueue
from app.models.audit import AuditEvent, AuditType
from app.models.jobs import DeadLetter, Job, JobKind, JobStatus

pytestmark = pytest.mark.integration


@dataclass
class Clock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def transport() -> Iterator[tuple[Redis, str]]:
    url = os.environ.get("TEST_REDIS_URL")
    if url is None:
        pytest.skip("Run PostgreSQL/Redis integration runner")
    redis = Redis.from_url(
        url, decode_responses=True, protocol=2, socket_timeout=5, socket_connect_timeout=5
    )
    namespace = "tai-test-" + uuid4().hex
    assert redis.ping()
    try:
        yield redis, namespace
    finally:
        # Exact test-owned stream only; never FLUSHDB, scan-delete or owner keys.
        redis.delete(namespace + ":jobs")
        redis.close()


def test_idempotent_job_duplicate_delivery_and_tracing(
    database: Database, transport: tuple[Redis, str], caplog: pytest.LogCaptureFixture
) -> None:
    redis, namespace = transport
    key, correlation = uuid4(), uuid4()
    with database.transaction() as session:
        job = enqueue(
            session, idempotency_key=key, correlation_id=correlation, queue_name=namespace
        )
        identity = job.id
    with database.transaction() as session:
        assert (
            enqueue(session, idempotency_key=key, correlation_id=uuid4(), queue_name=namespace).id
            == identity
        )
    with pytest.raises(ValueError, match="conflicts"):
        with database.transaction() as session:
            enqueue(
                session,
                idempotency_key=key,
                correlation_id=correlation,
                max_attempts=2,
                queue_name=namespace,
            )
    queue = JobQueue(database, redis, consumer="first", namespace=namespace, reclaim_ms=0)
    queue.prepare()
    caplog.set_level(logging.INFO)
    assert queue.dispatch_due() == 1
    assert queue.process_one(block_ms=1)
    for _ in range(2):
        redis.xadd(queue.stream, {"job_id": str(identity)})
        assert queue.process_one(block_ms=1)
    with database.transaction() as session:
        job = session.get(Job, identity)
        assert job is not None and job.status is JobStatus.SUCCEEDED and job.attempts == 1
        assert (
            session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.id == identity)
            )
            == 1
        )
    assert str(correlation) in caplog.text


def test_retry_backoff_dead_letter_and_handler_rollback(
    database: Database, transport: tuple[Redis, str], caplog: pytest.LogCaptureFixture
) -> None:
    redis, namespace = transport
    clock = Clock(utc_now())
    correlation = uuid4()
    with database.transaction() as session:
        job = enqueue(
            session, idempotency_key=uuid4(), correlation_id=correlation, queue_name=namespace
        )
        job.next_attempt_at = clock.now
        job.dispatch_after = clock.now
        identity = job.id
        before = session.scalar(select(func.count()).select_from(AuditEvent))

    def fail(session: Session, job: Job) -> None:
        append_event(session, event_type=AuditType.SYSTEM, correlation_id=job.correlation_id)
        raise RuntimeError("synthetic-sensitive-canary")

    queue = JobQueue(
        database,
        redis,
        consumer="fails",
        namespace=namespace,
        clock=clock,
        handlers={JobKind.AUDIT_CHECKPOINT: fail},
        reclaim_ms=0,
    )
    queue.prepare()
    for attempt in range(1, 4):
        assert queue.dispatch_due() == 1
        assert queue.process_one(block_ms=1)
        with database.transaction() as session:
            job = session.get(Job, identity)
            assert job is not None and job.attempts == attempt
            assert job.status is (JobStatus.DEAD if attempt == 3 else JobStatus.RETRY)
            assert session.scalar(select(func.count()).select_from(AuditEvent)) == before
            if attempt < 3:
                assert job.next_attempt_at == clock.now + timedelta(seconds=2 ** (attempt - 1))
        if attempt < 3:
            assert queue.dispatch_due() == 0
            clock.now += timedelta(seconds=2 ** (attempt - 1))
    with database.transaction() as session:
        letter = session.scalars(select(DeadLetter).where(DeadLetter.job_id == identity)).one()
        assert letter.correlation_id == correlation and letter.attempts == 3
        assert letter.error_code == "HANDLER_FAILED"
    assert queue.dispatch_due() == 0
    assert "synthetic-sensitive-canary" not in caplog.text


def test_pending_message_reclaimed_after_worker_restart(
    database: Database, transport: tuple[Redis, str]
) -> None:
    redis, namespace = transport
    queue = JobQueue(database, redis, consumer="abandoned", namespace=namespace, reclaim_ms=0)
    queue.prepare()
    with database.transaction() as session:
        identity = enqueue(
            session, idempotency_key=uuid4(), correlation_id=uuid4(), queue_name=namespace
        ).id
    queue.dispatch_due()
    assert redis.xreadgroup(queue.group, "abandoned", {queue.stream: ">"}, count=1)
    restarted = JobQueue(database, redis, consumer="restarted", namespace=namespace, reclaim_ms=0)
    assert restarted.process_one(block_ms=1)
    with database.transaction() as session:
        job = session.get(Job, identity)
        assert job is not None and job.status is JobStatus.SUCCEEDED and job.attempts == 1


def test_malformed_transport_never_creates_or_executes_job(
    database: Database, transport: tuple[Redis, str]
) -> None:
    redis, namespace = transport
    queue = JobQueue(database, redis, consumer="negative", namespace=namespace, reclaim_ms=0)
    queue.prepare()
    with database.transaction() as session:
        before = session.scalar(select(func.count()).select_from(Job))
    redis.xadd(queue.stream, {"not_job_id": "synthetic-untrusted-value"})
    assert queue.process_one(block_ms=1)
    with database.transaction() as session:
        assert session.scalar(select(func.count()).select_from(Job)) == before
        other = enqueue(
            session,
            idempotency_key=uuid4(),
            correlation_id=uuid4(),
            queue_name="other-" + uuid4().hex,
        )
        other_id = other.id
    redis.xadd(queue.stream, {"job_id": str(other_id)})
    assert queue.process_one(block_ms=1)
    with database.transaction() as session:
        other = session.get(Job, other_id)
        assert other is not None and other.status is JobStatus.READY and other.attempts == 0
