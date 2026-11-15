"""Operator-only enqueue of a non-financial PAPER audit checkpoint."""

import argparse
from uuid import UUID, uuid4

from app.database import Database
from app.job_queue import enqueue
from app.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idempotency-key", type=UUID, default=None)
    args = parser.parse_args()
    database = Database(load_settings())
    try:
        with database.transaction() as session:
            job = enqueue(
                session, idempotency_key=args.idempotency_key or uuid4(), correlation_id=uuid4()
            )
            identity, correlation = job.id, job.correlation_id
        print(f"job_id={identity} correlation_id={correlation}")
    finally:
        database.close()


if __name__ == "__main__":
    main()
