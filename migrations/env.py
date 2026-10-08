"""Versioned migrations use the same mandatory database URL as the app."""
from alembic import context
from backend.database.postgres import application_engine

with application_engine().connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
