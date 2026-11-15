"""Validate rendered development isolation policy without printing credentials."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--docker-config")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
command = ["docker"]
if args.docker_config:
    command += ["--config", args.docker_config]
command += ["compose", "--profile", "tools", "-f", str(root / "infrastructure" / "compose.yaml")]
result = subprocess.run(
    command + ["--env-file", str(root / "infrastructure" / ".env"), "config", "--format", "json"],
    capture_output=True,
    text=True,
    timeout=30,
)
if result.returncode:
    raise SystemExit("Compose config failed; check local .env (values intentionally not printed)")
config = json.loads(result.stdout)
assert config["name"] == "trading-ai-dev"
assert set(config["services"]) == {"postgres", "redis", "backend", "migrate", "worker"}
for name, service in config["services"].items():
    assert not service.get("privileged", False), name
    assert service.get("network_mode") != "host", name
    assert service["restart"] == "no", name
    if name != "migrate":
        assert service["healthcheck"]["test"], name
    assert all(port["host_ip"] == "127.0.0.1" for port in service.get("ports", [])), name
    assert all(volume["type"] != "bind" for volume in service.get("volumes", [])), name
backend = config["services"]["backend"]
assert backend["environment"]["TAI_TRADING_MODE"] == "PAPER"
assert backend["environment"]["TAI_FEED_PROVIDER"] == "FIXTURE"
assert "trading_ai_app:" in backend["environment"]["TAI_DATABASE_URL"]
assert config["services"]["migrate"]["profiles"] == ["tools"]
assert not config["services"]["migrate"].get("ports")
assert backend["read_only"] is True
assert "ALL" in backend["cap_drop"]
assert all(
    dependency["condition"] == "service_healthy" for dependency in backend["depends_on"].values()
)
assert set(config["volumes"]) == {"postgres-data", "redis-data"}
print("PASS: isolated project, PAPER fixture backend, localhost ports, healthchecks, named volumes")
print("PASS: no privileged, host network or bind-mount access")

environment = {
    key: value
    for key, value in os.environ.items()
    if key not in {"POSTGRES_PASSWORD", "REDIS_PASSWORD"}
}
with tempfile.TemporaryDirectory() as temp:
    empty = Path(temp) / ".env"
    empty.write_text("", encoding="utf-8")
    negative = subprocess.run(
        command + ["--env-file", str(empty), "config", "--quiet"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert negative.returncode != 0, "missing local credentials must fail closed"
print("PASS: missing local credentials reject Compose config")
