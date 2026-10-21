"""Alembic environment for the bot's state store (run from Store.__init__, never by hand needed).

`config.attributes["connection"]` is the SQLAlchemy connection to migrate; see store.migrate().
"""
from alembic import context

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=None, render_as_batch=True)
with context.begin_transaction():
    context.run_migrations()
