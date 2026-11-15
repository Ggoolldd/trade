"""Coalesced UTC intervals with transactional advisory locks and stable job keys."""

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.database import Database
from app.domain_types import require_utc, utc_now
from app.job_queue import enqueue
from app.models.jobs import JobStatus
from app.models.schedules import Schedule, ScheduledRun


def lock_key(identity: UUID) -> int:
    return int.from_bytes(hashlib.sha256(identity.bytes).digest()[:8], "big", signed=True)


class Scheduler:
    def __init__(self, database: Database, clock: Callable[[], datetime] = utc_now) -> None:
        self.database, self.clock = database, clock

    def tick(self, limit: int = 20) -> list[UUID]:
        if not 1 <= limit <= 100:
            raise ValueError("scheduler limit must be 1 through 100")
        now = require_utc(self.clock())
        jobs = []
        with self.database.transaction() as session:
            due = session.scalars(
                select(Schedule)
                .where(
                    Schedule.enabled.is_(True),
                    Schedule.next_run_at <= now,
                )
                .order_by(Schedule.next_run_at, Schedule.id)
                .with_for_update(skip_locked=True)
                .limit(limit)
            ).all()
            for schedule in due:
                if not session.scalar(
                    select(func.pg_try_advisory_xact_lock(lock_key(schedule.id)))
                ):
                    continue
                period = timedelta(seconds=schedule.interval_seconds)
                # Skip missed periods deliberately; enqueue only the latest due slot.
                slot = schedule.next_run_at + ((now - schedule.next_run_at) // period) * period
                identity = uuid5(
                    NAMESPACE_URL, f"trading-ai:schedule:{schedule.id}:{slot.isoformat()}"
                )
                job = enqueue(
                    session,
                    idempotency_key=identity,
                    correlation_id=identity,
                    entity_id=schedule.id,
                    kind=schedule.kind,
                    queue_name=schedule.queue_name,
                )
                if job.status is JobStatus.READY and job.attempts == 0:
                    job.next_attempt_at = now
                    job.dispatch_after = now
                session.execute(
                    insert(ScheduledRun)
                    .values(
                        schedule_id=schedule.id,
                        scheduled_at=slot,
                        job_id=job.id,
                    )
                    .on_conflict_do_nothing(index_elements=["schedule_id", "scheduled_at"])
                )
                schedule.next_run_at = slot + period
                jobs.append(job.id)
        return jobs
