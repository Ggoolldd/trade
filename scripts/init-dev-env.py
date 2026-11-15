"""Generate local-only database passwords; never overwrite an existing env file."""

import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / "infrastructure" / ".env"
contents = target.read_text(encoding="utf-8") if target.exists() else ""
present = {line.split("=", 1)[0].strip() for line in contents.splitlines() if "=" in line}
missing = [
    name
    for name in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "POSTGRES_APP_PASSWORD")
    if name not in present
]
if missing:
    with target.open("a" if target.exists() else "x", encoding="utf-8", newline="\n") as stream:
        if contents and not contents.endswith("\n"):
            stream.write("\n")
        for name in missing:
            stream.write(f"{name}={secrets.token_hex(32)}\n")
    print("Added missing local credential fields; existing values preserved; secrets not printed")
else:
    print("Existing infrastructure/.env preserved")
