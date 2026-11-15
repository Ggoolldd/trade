# Local PAPER infrastructure

From the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/init-dev-env.py
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml config --quiet
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml up --build -d --wait --wait-timeout 120
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml ps
```

The first command generates random development-only PostgreSQL and Redis passwords
into ignored `infrastructure/.env`; it preserves an existing file. Do not print
expanded Compose config or container environment into shared logs. The examples
contain no broker credentials.

Project `trading-ai-dev` has its own network and named `postgres-data`/`redis-data`
volumes. No bind mounts of other projects, privileged containers or host networking.
Ports bind localhost: backend 18000, PostgreSQL 15432, Redis 16379. If a port is
occupied, resolve the mapping deliberately; never stop an unrelated container.

Backend image installs production dependencies from uv.lock, runs UID 10001 with
read-only root filesystem, dropped capabilities and temporary /tmp. Database
images manage their own data-directory permissions. All services have healthchecks;
backend starts after DB and Redis are healthy. API readiness still covers process
lifecycle; it is not yet a continuous dependency-connectivity check.

All containers use `restart: no` to avoid accidental startup during later daemon
restarts. For a non-destructive shutdown, stop only this Compose project:

```powershell
docker compose --env-file infrastructure/.env -f infrastructure/compose.yaml stop
```

Do not delete volumes. Changing a password in .env does not rotate an already
initialized DB; preserve the file and use a deliberate rotation procedure later.
This is development infrastructure, not a production or LIVE deployment.

## Version and license selection

Explicit tags: Python 3.12.16-slim-bookworm, PostgreSQL 17.12-bookworm,
Redis 7.2.17-bookworm, uv 0.13.8. Tags are version-pinned but mutable; immutable
digest pinning and image scanning belong to TAI-163/174 before release.
Redis 7.2.17 was selected with its upstream BSD-style
[COPYING](https://github.com/redis/redis/blob/7.2.17/COPYING) reviewed; this does
not assert the same license for newer Redis branches. Runtime images have their
own third-party license notices. No project license has been granted.

Sources checked for TAI-013:
[Compose health dependencies](https://docs.docker.com/compose/how-tos/startup-order/),
[uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/),
[PostgreSQL image](https://hub.docker.com/_/postgres),
[Redis image](https://hub.docker.com/_/redis),
[Python image](https://hub.docker.com/_/python).

## Verified runtime and WSL recovery

TAI-013 passed after recovery of an initial DockerDesktop/Wsl/CommandTimedOut.
The owner explicitly requested WSL reset. The initial `wsl --shutdown`
stalled in StopPending; an administrator reset of WslService succeeded and
`wsl --list --quiet` returned Ubuntu and docker-desktop. Docker Desktop was
restarted. No distribution/volume deletion, factory reset or host restart was
performed. Docker engine 29.9.3 then responded; build succeeded and all three
services became healthy. Actual image IDs, PostgreSQL query, Redis authenticated
PING and both backend health routes passed. Evidence:
[runtime smoke](../docs/reports/TAI-013-smoke.txt).

Repeat runtime verification with:

```powershell
backend/.venv/Scripts/python.exe scripts/smoke-compose.py
```

Config policy check (does not require a running engine):

```powershell
backend/.venv/Scripts/python.exe scripts/check-compose.py
```

For this sandbox's isolated Docker CLI config, append
`--docker-config D:\TRADING\tmp\docker`. It checks localhost binding, named
volumes, PAPER mode, health dependencies and missing-credential rejection without
printing rendered passwords. Local health status is not broker connectivity proof.
