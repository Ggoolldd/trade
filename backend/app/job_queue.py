"""At-least-once Redis delivery with transactional, idempotent DB effects."""

import logging
import re
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from uuid import UUID

from redis import Redis
from redis.exceptions import ResponseError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.audit import append_event
from app.database import Database
from app.domain_types import TradingMode, utc_now
from app.models.audit import AuditType
from app.models.jobs import DeadLetter, Job, JobKind, JobStatus

logger = logging.getLogger(__name__)
Handler = Callable[[Session, Job], None]


def checkpoint(session: Session, job: Job) -> None:
    append_event(
        session,
        event_type=AuditType.SYSTEM,
        correlation_id=job.correlation_id,
        entity_id=job.entity_id or job.id,
        event_id=job.id,
    )


def enqueue(
    session: Session,
    *,
    idempotency_key: UUID,
    correlation_id: UUID,
    kind: JobKind = JobKind.AUDIT_CHECKPOINT,
    entity_id: UUID | None = None,
    max_attempts: int = 3,
    queue_name: str = "trading-ai",
) -> Job:
    session.execute(
        insert(Job)
        .values(
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            kind=kind,
            entity_id=entity_id,
            max_attempts=max_attempts,
            queue_name=queue_name,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
    )
    job = session.scalars(select(Job).where(Job.idempotency_key == idempotency_key)).one()
    if (job.kind, job.entity_id, job.max_attempts, job.queue_name) != (
        kind,
        entity_id,
        max_attempts,
        queue_name,
    ):
        raise ValueError("idempotency key conflicts with different job")
    return job


class JobQueue:
    def __init__(
        self,
        database: Database,
        redis: Redis,
        *,
        consumer: str,
        namespace: str = "trading-ai",
        clock: Callable[[], datetime] = utc_now,
        handlers: Mapping[JobKind, Handler] | None = None,
        reclaim_ms: int = 60000,
    ) -> None:
        self.database, self.redis, self.consumer = database, redis, consumer
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:-]{0,99}", namespace):
            raise ValueError("invalid queue namespace")
        self.namespace = namespace
        self.stream, self.group = namespace + ":jobs", namespace + ":workers"
        self.clock, self.reclaim_ms = clock, reclaim_ms
        self.handlers = handlers if handlers is not None else {JobKind.AUDIT_CHECKPOINT: checkpoint}

    def prepare(self) -> None:
        try:
            self.redis.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    def dispatch_due(self, limit: int = 20) -> int:
        if not 1 <= limit <= 100:
            raise ValueError("dispatch limit must be 1 through 100")
        now = self.clock()
        with self.database.transaction() as session:
            due = session.scalars(
                select(Job)
                .where(
                    Job.status.in_([JobStatus.READY, JobStatus.RETRY]),
                    Job.mode == TradingMode.PAPER,
                    Job.queue_name == self.namespace,
                    Job.next_attempt_at <= now,
                    Job.dispatch_after <= now,
                )
                .order_by(Job.created_at, Job.id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            for job in due:
                self.redis.xadd(self.stream, {"job_id": str(job.id)})
                job.dispatch_after = now + timedelta(seconds=60)
            return len(due)

    def execute(self, identity: UUID) -> None:
        now = self.clock()
        with self.database.transaction() as session:
            job = session.get(Job, identity, with_for_update=True)
            if job is None:
                logger.warning("queue_unknown_job")
                return
            if job.queue_name != self.namespace:
                logger.warning("queue_wrong_namespace")
                return
            if job.mode is not TradingMode.PAPER:
                raise ValueError("non-PAPER job forbidden")
            if job.status not in {JobStatus.READY, JobStatus.RETRY} or job.next_attempt_at > now:
                return
            job.attempts += 1
            session.flush()
            try:
                with session.begin_nested():
                    self.handlers[job.kind](session, job)
            except Exception:
                job.last_error_code = "HANDLER_FAILED"
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.DEAD
                    session.add(
                        DeadLetter(
                            job_id=job.id,
                            correlation_id=job.correlation_id,
                            attempts=job.attempts,
                            error_code="HANDLER_FAILED",
                        )
                    )
                else:
                    job.status = JobStatus.RETRY
                    job.next_attempt_at = now + timedelta(seconds=min(60, 2 ** (job.attempts - 1)))
                    job.dispatch_after = job.next_attempt_at
            else:
                job.status = JobStatus.SUCCEEDED
                job.last_error_code = None
        if job.status is JobStatus.SUCCEEDED:
            logger.info("job_succeeded job_id=%s correlation_id=%s", job.id, job.correlation_id)
        else:
            logger.warning(
                "job_failed job_id=%s correlation_id=%s code=HANDLER_FAILED",
                job.id,
                job.correlation_id,
            )

    def process_one(self, block_ms: int = 1000) -> bool:
        claimed = self.redis.xautoclaim(
            self.stream,
            self.group,
            self.consumer,
            min_idle_time=self.reclaim_ms,
            start_id="0-0",
            count=1,
        )
        messages = claimed[1]
        if not messages:
            groups = self.redis.xreadgroup(
                self.group, self.consumer, {self.stream: ">"}, count=1, block=block_ms
            )
            if isinstance(groups, dict):
                raise ValueError("worker transport requires RESP2")
            messages = groups[0][1] if groups else []
        if not messages:
            return False
        message_id, fields = messages[0]
        try:
            identity = UUID(fields["job_id"])
        except (KeyError, ValueError, TypeError):
            logger.warning("queue_malformed_message")
        else:
            # ACK only after DB transaction commits; crash reclaims pending delivery.
            self.execute(identity)
        self.redis.xack(self.stream, self.group, message_id)
        self.redis.xdel(self.stream, message_id)
        return True
