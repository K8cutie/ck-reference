# alembic/env.py
import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool

# --- Logging ---------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- PYTHONPATH so we can import project modules ---------------------------
# Run alembic from the repo root.
sys.path.insert(0, os.getcwd())

# --- Load metadata (best-effort: app.db then db) ---------------------------
Base = None
try:
    from app.db import Base as _Base  # app/ layout
    Base = _Base
except Exception:
    try:
        from db import Base as _Base  # flat layout
        Base = _Base
    except Exception:
        Base = None

target_metadata = Base.metadata if Base else None

# --- URL resolution: prefer .env (DATABASE_URL), fallback to alembic.ini ---
def get_db_url() -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")

# --- Offline ---------------------------------------------------------------
def run_migrations_offline() -> None:
    url = get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="public",
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# --- Online ----------------------------------------------------------------
def run_migrations_online() -> None:
    url = get_db_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="public",
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
