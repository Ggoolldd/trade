"""Enqueue one real non-financial job and observe the separate local worker."""

import re
import time
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy import func, select

# Run with backend as import root; the script never invokes a handler itself.
from app.database import Database
from app.job_queue import enqueue
from app.models.audit import AuditEvent
from app.models.jobs import Job, JobStatus
from app.settings import Settings

root = Path(__file__).resolve().parents[1]
password = dotenv_values(root / "infrastructure" / ".env").get("POSTGRES_APP_PASSWORD")
if not password or not re.fullmatch(r"[a-f0-9]{64}", password):
    raise SystemExit("Missing generated local runtime credential")
database = Database(
    Settings(
        database_url=SecretStr(
            f"postgresql+psycopg://trading_ai_app:{password}@127.0.0.1:15432/trading_ai"
        )
    )
)
try:
    key, correlation = uuid4(), uuid4()
    with database.transaction() as session:
        identity = enqueue(session, idempotency_key=key, correlation_id=correlation).id
    with database.transaction() as session:
        assert enqueue(session, idempotency_key=key, correlation_id=uuid4()).id == identity
    deadline = time.monotonic() + 20
    while True:
        with database.transaction() as session:
            job = session.get(Job, identity)
            assert job is not None
            if job.status is JobStatus.SUCCEEDED:
                assert job.attempts == 1
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(AuditEvent)
                        .where(AuditEvent.id == identity)
                    )
                    == 1
                )
                print(
                    f"PASS: separate worker committed job {identity}, attempts=1, audit effects=1"
                )
                print(f"TRACE: correlation_id={correlation}")
                break
            assert job.status is not JobStatus.DEAD, "checkpoint unexpectedly dead-lettered"
        if time.monotonic() > deadline:
            raise SystemExit("Worker did not finish within 20s; no success claimed")
        time.sleep(0.2)
finally:
    database.close()
