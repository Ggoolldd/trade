"""Check actual project containers and loopback API without exposing env values."""

import argparse
import json
import subprocess
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--docker-config")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
docker = ["docker"]
if args.docker_config:
    docker += ["--config", args.docker_config]
compose = docker + [
    "compose",
    "--env-file",
    str(root / "infrastructure" / ".env"),
    "-f",
    str(root / "infrastructure" / "compose.yaml"),
]


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise SystemExit(
            "Container smoke command failed; inspect Docker status without dumping env"
        )
    return result.stdout.strip()


raw = run(compose + ["ps", "--format", "json"])
rows = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]
assert {row["Service"] for row in rows} == {"postgres", "redis", "backend"}
for row in rows:
    assert row["State"] == "running", row["Service"]
    assert row["Health"] == "healthy", row["Service"]
    print(f"PASS: {row['Service']} running/healthy; container {row['ID']}")
    image = run(docker + ["inspect", "--format", "{{.Image}}", row["ID"]])
    print(f"IMAGE: {row['Service']} {image}")
assert run(compose + ["exec", "-T", "backend", "id", "-u"]) == "10001"
print("PASS: backend UID 10001")
backend = next(row for row in rows if row["Service"] == "backend")
assert (
    run(docker + ["inspect", "--format", "{{.HostConfig.ReadonlyRootfs}}", backend["ID"]]) == "true"
)
print("PASS: backend read-only root filesystem")
assert run(compose + ["exec", "-T", "redis", "redis-cli", "ping"]) == "PONG"
print("PASS: Redis authenticated PONG")
assert (
    run(
        compose
        + [
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "trading",
            "-d",
            "trading_ai",
            "-Atc",
            "SELECT current_database()",
        ]
    )
    == "trading_ai"
)
print("PASS: PostgreSQL query on trading_ai")
with httpx.Client(base_url="http://127.0.0.1:18000", timeout=10, trust_env=False) as client:
    for path, expected in [("/health/live", "alive"), ("/health/ready", "ready")]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == {"status": expected, "mode": "PAPER", "scope": "process"}
        print(f"PASS: {path} 200 PAPER scope=process")
    assert client.get("/openapi.json").status_code == 200
    assert client.post("/api/v1/orders", json={}).status_code == 404
print("PASS: OpenAPI 200; order route absent (404)")
