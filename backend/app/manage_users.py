"""Operator-only local user creation; no password in shell arguments or output."""

import argparse
from getpass import getpass
from uuid import uuid4

from pydantic import SecretStr

from app.audit import append_event
from app.auth import create_user
from app.database import Database
from app.models.audit import AuditReason, AuditType
from app.models.auth import UserRole
from app.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--role", choices=[role.value for role in UserRole], default="readonly")
    args = parser.parse_args()
    password = getpass("New local password (15–128 characters): ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords do not match")
    database = Database(load_settings())
    try:
        with database.transaction() as session:
            user = create_user(
                session, username=args.username, password=SecretStr(password), enabled=True
            )
            user.role = UserRole(args.role)
            append_event(
                session,
                event_type=AuditType.ACCOUNT_CHANGED,
                correlation_id=uuid4(),
                actor_id=user.id,
                entity_id=user.id,
                reason=AuditReason.USER_ACTION,
            )
        print("Local user created; password not printed. No per-account trading grants added.")
    finally:
        database.close()


if __name__ == "__main__":
    main()
