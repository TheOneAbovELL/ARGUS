"""Alembic migrations: clean upgrade, no model drift, idempotence, downgrade."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR
from app.db.models import Base
from app.db.session import run_migrations, sync_url

POSTGRES_URL = os.getenv("ARGUS_TEST_POSTGRES_URL")  # e.g. postgresql+psycopg://argus:argus@localhost/argus_test


@pytest.mark.parametrize("backend", ["sqlite", pytest.param("postgres", marks=pytest.mark.skipif(
    not POSTGRES_URL, reason="set ARGUS_TEST_POSTGRES_URL to test migrations on PostgreSQL"))])
def test_migrations_upgrade_match_models_and_downgrade(tmp_path: Path, backend: str) -> None:
    url = POSTGRES_URL if backend == "postgres" else f"sqlite+aiosqlite:///{(tmp_path / 'm.db').as_posix()}"
    run_migrations(url)
    engine = create_engine(sync_url(url))
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        assert {"users", "sessions", "portfolios", "portfolio_holdings", "watchlist_items",
                "research_reports", "documents", "alembic_version"} <= tables
        drift = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert drift == [], f"models and migrations differ: {drift}"

    run_migrations(url)  # re-running at head is a no-op

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", sync_url(url))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
    engine.dispose()
