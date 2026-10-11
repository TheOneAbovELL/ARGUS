"""Async engine/session management and migration helpers."""

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import BACKEND_DIR

logger = logging.getLogger("argus.db")


def sync_url(async_url: str) -> str:
    """Alembic runs synchronously; map async driver URLs to sync ones."""
    return async_url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        if url.startswith("sqlite"):
            path = url.split(":///", 1)[-1]
            if path and path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _sqlite_pragmas)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:  # readiness probe: report, don't raise
            logger.warning("database ping failed", exc_info=True)
            return False

    async def dispose(self) -> None:
        await self.engine.dispose()


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")  # required for ON DELETE CASCADE
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def run_migrations(url: str, revision: str = "head") -> None:
    """Apply Alembic migrations (blocking; call via ``asyncio.to_thread``)."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", sync_url(url))
    config.attributes["configure_logger"] = False
    command.upgrade(config, revision)
