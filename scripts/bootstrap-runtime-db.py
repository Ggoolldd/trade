"""Configure a local non-owner runtime role using only generated dev credentials."""

import re
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql

root = Path(__file__).resolve().parents[1]
values = dotenv_values(root / "infrastructure" / ".env")
admin_password = values.get("POSTGRES_PASSWORD")
app_password = values.get("POSTGRES_APP_PASSWORD")
if not all(
    value and re.fullmatch(r"[a-f0-9]{64}", value) for value in [admin_password, app_password]
):
    raise SystemExit("Expected generated local passwords; run init-dev-env.py")
with psycopg.connect(
    host="127.0.0.1",
    port=15432,
    dbname="trading_ai",
    user="trading",
    password=admin_password,
    connect_timeout=5,
) as connection:
    role = connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname='trading_ai_app'"
    ).fetchone()
    if role is None:
        connection.execute(
            sql.SQL(
                "CREATE ROLE trading_ai_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Literal(app_password))
        )
    else:
        if any(role):
            raise SystemExit("Existing runtime role has excessive privileges; refusing bootstrap")
        connection.execute(
            sql.SQL("ALTER ROLE trading_ai_app PASSWORD {}").format(sql.Literal(app_password))
        )
    memberships = connection.execute(
        "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
        "WHERE r.rolname='trading_ai_app' LIMIT 1"
    ).fetchone()
    if memberships:
        raise SystemExit("Unexpected role membership; refusing bootstrap")
    owner = connection.execute(
        "SELECT 1 FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner "
        "WHERE r.rolname='trading_ai_app' LIMIT 1"
    ).fetchone()
    if owner:
        raise SystemExit("Runtime role unexpectedly owns database objects; refusing bootstrap")
    connection.execute("GRANT CONNECT ON DATABASE trading_ai TO trading_ai_app")
    connection.execute("GRANT USAGE ON SCHEMA trading, public TO trading_ai_app")
    connection.execute("GRANT SELECT ON public.alembic_version TO trading_ai_app")
    connection.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA trading TO trading_ai_app"
    )
    connection.execute(
        "REVOKE UPDATE, DELETE, TRUNCATE ON trading.audit_events FROM trading_ai_app"
    )
    connection.execute("REVOKE CREATE ON SCHEMA trading, public FROM trading_ai_app")
print(
    "PASS: local trading_ai_app role configured; "
    "no owner/DDL/admin privileges; audit SELECT/INSERT only"
)
