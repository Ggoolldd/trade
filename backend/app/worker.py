"""Non-financial job worker with heartbeat and graceful termination."""

import argparse
import logging
import signal
import socket
import time

from redis import Redis

from app.database import Database
from app.job_queue import JobQueue
from app.scheduler import Scheduler
from app.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        protocol=2,
    )
    consumer = socket.gethostname()
    heartbeat = "trading-ai:heartbeat:" + consumer
    if args.health:
        try:
            raise SystemExit(0 if redis.get(heartbeat) else 1)
        finally:
            redis.close()
    logging.basicConfig(level=logging.INFO)
    database = Database(settings)
    running = True

    def stop(signum: int, frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    queue = JobQueue(database, redis, consumer=consumer)
    scheduler = Scheduler(database)
    try:
        while running:
            try:
                queue.prepare()
                scheduler.tick()
                queue.dispatch_due()
                queue.process_one()
                redis.set(heartbeat, "ready", ex=30)
            except Exception:
                logging.error("queue_dependency_failure mode=PAPER")
                if args.once:
                    raise SystemExit(1) from None
                time.sleep(1)
            if args.once:
                break
    finally:
        database.close()
        redis.close()


if __name__ == "__main__":
    main()
