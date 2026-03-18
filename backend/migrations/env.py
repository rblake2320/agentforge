"""
Alembic environment — synchronous engine, agentforge schema.

env.py runs in two modes:
  offline  — emits SQL to stdout (alembic upgrade --sql)
  online   — connects to the DB and runs migrations directly

Schema creation (CREATE SCHEMA IF NOT EXISTS agentforge) happens
automatically in online mode before the migration context is opened.

The module is also safe to `import` outside the Alembic CLI (e.g. for
syntax-checking or test discovery): all alembic.context proxy access is
deferred inside functions and guarded at the bottom.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context

# ---------------------------------------------------------------------------
# Make the repo root (D:/agentvault) importable so that
# `from backend.models import Base` works regardless of cwd.
# ---------------------------------------------------------------------------
_here = os.path.dirname(__file__)                          # .../backend/migrations
_backend_dir = os.path.dirname(_here)                      # .../backend
_root_dir = os.path.dirname(_backend_dir)                  # .../agentvault
for _p in (_root_dir, _backend_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.models import Base, SCHEMA  # noqa: E402

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generate raw SQL without a live DB connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    cfg = context.config

    if cfg.config_file_name is not None:
        fileConfig(cfg.config_file_name)

    _apply_db_url(cfg)

    url = cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connect and migrate
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    cfg = context.config

    if cfg.config_file_name is not None:
        fileConfig(cfg.config_file_name)

    _apply_db_url(cfg)

    connectable = engine_from_config(
        cfg.get_section(cfg.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Ensure the schema exists before Alembic tries to create the
        # alembic_version table inside it.
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=SCHEMA,
        )

        with context.begin_transaction():
            context.run_migrations()


def _apply_db_url(cfg) -> None:  # type: ignore[type-arg]
    """Override sqlalchemy.url from Settings when available."""
    try:
        from backend.config import get_settings as _get_settings
        _settings = _get_settings()
        cfg.set_main_option("sqlalchemy.url", _settings.database_url)
    except Exception:
        # In CI / offline mode without a .env, use the ini value as-is.
        pass


# ---------------------------------------------------------------------------
# Entry point — only runs when Alembic CLI invokes this file.
# alembic.context.is_offline_mode() raises AttributeError when accessed
# outside the CLI runner, so we guard with a try/except.
# ---------------------------------------------------------------------------
try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
except (AttributeError, NameError):
    # Module is being imported for inspection only (not via `alembic` CLI).
    # The alembic.context proxy is not initialised outside the CLI runner.
    pass
