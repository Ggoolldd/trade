"""Generate local-only database passwords; never overwrite an existing env file."""

import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / "infrastructure" / ".env"
if target.exists():
    print("Existing infrastructure/.env preserved")
else:
    contents = (
        "# Local development only. Do not commit or reuse for brokers/production.\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(32)}\n"
        f"REDIS_PASSWORD={secrets.token_hex(32)}\n"
    )
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(contents)
    print("Created ignored infrastructure/.env with random local passwords (values not printed)")
