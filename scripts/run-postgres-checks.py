"""Create a new isolated test DB, run tests, and remove only that newly-created DB."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql

parser = argparse.ArgumentParser()
parser.add_argument("task")
args = parser.parse_args()
if not re.fullmatch(r"TAI-\d{3}", args.task):
    parser.error("expected TAI-XXX")
root = Path(__file__).resolve().parents[1]
secrets = dotenv_values(root / "infrastructure" / ".env")
password = secrets.get("POSTGRES_PASSWORD")
if not password or not re.fullmatch(r"[a-f0-9]{64}", password):
    raise SystemExit("Expected generated local-only PostgreSQL password; values not printed")
name = "tai_test_" + uuid4().hex
created = False
with (root / "docs" / "reports" / f"{args.task}-postgres.txt").open("w", encoding="utf-8") as log:
    with psycopg.connect(
        host="127.0.0.1",
        port=15432,
        user="trading",
        password=password,
        dbname="postgres",
        autocommit=True,
        connect_timeout=5,
    ) as admin:
        try:
            version = admin.execute("SHOW server_version").fetchone()
            log.write(f"PostgreSQL server: {version}\n")
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
            print(f"Created isolated test database {name}", flush=True)
            environment = dict(os.environ)
            environment["TEST_DATABASE_URL"] = (
                f"postgresql+psycopg://trading:{password}@127.0.0.1:15432/{name}"
            )
            temporary = root / "tmp" / ("pytest-postgres-" + uuid4().hex)
            assert not temporary.exists()
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--maxfail=3",
                "--tb=short",
                "--basetemp",
                str(temporary),
            ]
            log.write(
                "COMMAND: python -m pytest -q --maxfail=3 --tb=short "
                "--basetemp <new workspace tmp> (TEST_DATABASE_URL set; value redacted)\n"
            )
            result = subprocess.run(
                command,
                cwd=root / "backend",
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            output = result.stdout + result.stderr
            output = output.replace(password, "[REDACTED]")
            print(output, end="", flush=True)
            log.write(output)
            log.write(f"EXIT CODE: {result.returncode}\n")
            if result.returncode:
                raise SystemExit(result.returncode)
        finally:
            if created:
                assert re.fullmatch(r"tai_test_[a-f0-9]{32}", name)
                # Never accepts an owner-provided DB name and never uses FORCE.
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
                log.write(f"Removed newly-created ephemeral test database {name}\n")
                print("Removed only the newly-created test database; project DB/volumes preserved")
