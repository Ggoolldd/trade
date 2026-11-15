from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.database import Database
from app.domain_types import utc_now
from app.job_queue import enqueue
from app.models.jobs import Job, JobKind
from app.models.schedules import Schedule, ScheduledRun
from app.scheduler import Scheduler, lock_key

pytestmark = pytest.mark.integration


@pytest.fixture
def schedule(database: Database) -> Iterator[UUID]:
    with database.transaction() as session:
        row = Schedule(
            name="test-" + uuid4().hex,
            queue_name="test-" + uuid4().hex,
            kind=JobKind.AUDIT_CHECKPOINT,
            interval_seconds=60,
            next_run_at=utc_now() - timedelta(hours=1),
            enabled=True,
        )
        session.add(row)
        session.flush()
        identity = row.id
    try:
        yield identity
    finally:
        # Keep lineage but disable this test-owned schedule before the next test.
        with database.transaction() as session:
            row = session.get(Schedule, identity)
            assert row is not None
            row.enabled = False


def test_concurrent_start_and_restart_create_one_job_per_slot(
    database: Database, schedule: UUID
) -> None:
    now = utc_now()
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: Scheduler(database, lambda: now).tick(), range(8)))
    assert sum(len(batch) for batch in results) == 1
    assert Scheduler(database, lambda: now).tick() == []
    with database.transaction() as session:
        run = session.scalars(
            select(ScheduledRun).where(ScheduledRun.schedule_id == schedule)
        ).one()
        job = session.get(Job, run.job_id)
        assert job is not None and job.entity_id == schedule
        assert (
            session.scalar(
                select(func.count())
                .select_from(ScheduledRun)
                .where(ScheduledRun.schedule_id == schedule)
            )
            == 1
        )
    later = now + timedelta(seconds=60)
    assert len(Scheduler(database, lambda: later).tick()) == 1
    with database.transaction() as session:
        runs = session.scalars(
            select(ScheduledRun)
            .where(ScheduledRun.schedule_id == schedule)
            .order_by(ScheduledRun.scheduled_at)
        ).all()
        assert len(runs) == 2 and runs[0].job_id != runs[1].job_id


def test_advisory_lease_releases_when_connection_closes(database: Database, schedule: UUID) -> None:
    now = utc_now()
    with database.engine.begin() as connection:
        assert connection.scalar(select(func.pg_try_advisory_xact_lock(lock_key(schedule))))
        assert Scheduler(database, lambda: now).tick() == []
    assert len(Scheduler(database, lambda: now).tick()) == 1
    assert Scheduler(database, lambda: now).tick() == []


def test_crash_before_cursor_commit_rolls_back_job_and_cursor(
    database: Database, schedule: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = utc_now()
    with database.transaction() as session:
        original = session.get(Schedule, schedule)
        assert original is not None
        cursor = original.next_run_at

    def crash(*args: object, **kwargs: object) -> Job:
        enqueue(*args, **kwargs)
        raise RuntimeError("synthetic scheduler crash")

    with monkeypatch.context() as patched:
        patched.setattr("app.scheduler.enqueue", crash)
        with pytest.raises(RuntimeError, match="scheduler crash"):
            Scheduler(database, lambda: now).tick()
    with database.transaction() as session:
        original = session.get(Schedule, schedule)
        assert original is not None and original.next_run_at == cursor
        assert (
            session.scalar(select(func.count()).select_from(Job).where(Job.entity_id == schedule))
            == 0
        )
    assert len(Scheduler(database, lambda: now).tick()) == 1


def test_disabled_schedule_does_not_enqueue(database: Database, schedule: UUID) -> None:
    with database.transaction() as session:
        row = session.get(Schedule, schedule)
        assert row is not None
        row.enabled = False
    assert Scheduler(database).tick() == []
