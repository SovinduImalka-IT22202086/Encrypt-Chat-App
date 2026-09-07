"""Database engine and session management.

SQLite via `aiosqlite` for development. The repository layer talks only to the
SQLAlchemy ORM, so queries are parameterized by construction - no SQL string
concatenation anywhere (`SERVER-006`, and the SQL-injection surface Phase 0
flagged).

Only accounts and authentication sessions are stored. No message content, no
message keys, and no cryptographic identity private keys ever reach this
database (`SERVER-002`, `CRYPTO-002`).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.models import Base

#: Default development database. The path is git-ignored (`*.db`).
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./data/app.db"

#: In-memory URL used by tests.
MEMORY_DATABASE_URL = "sqlite+aiosqlite://"


def database_url() -> str:
    """Resolve the database URL from the environment."""
    configured = os.environ.get("DATABASE_URL", "").strip()
    return configured or DEFAULT_DATABASE_URL


def create_engine(url: str | None = None) -> AsyncEngine:
    """Create an async engine.

    An in-memory SQLite database lives inside a single connection, so tests
    must share one; `StaticPool` provides that. File-backed databases use the
    normal pool.
    """
    resolved = url if url is not None else database_url()

    if resolved == MEMORY_DATABASE_URL or ":memory:" in resolved:
        return create_async_engine(
            resolved,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )

    _ensure_parent_directory(resolved)
    return create_async_engine(resolved, future=True)


def _ensure_parent_directory(url: str) -> None:
    """Create the directory for a file-backed SQLite database if needed."""
    marker = "sqlite+aiosqlite:///"
    if not url.startswith(marker):
        return
    path = url[len(marker) :]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to an engine."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def create_schema(engine: AsyncEngine) -> None:
    """Create tables that do not yet exist.

    Adequate for Phase 3. A real migration tool is Phase 10's concern; this is
    recorded as a known limitation rather than presented as production-ready.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transactional session that rolls back on failure."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
