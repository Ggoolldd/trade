"""Alembic environment; database credentials never pass through ConfigParser."""

from alembic import context
from sqlalchemy import Connection

from app.database import Base, Database
from app.settings import load_settings

config = context.config


def migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=load_settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        migrate(supplied)
    else:
        database = Database(load_settings())
        try:
            with database.engine.connect() as connection:
                migrate(connection)
        finally:
            database.close()
