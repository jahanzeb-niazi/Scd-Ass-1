"""
Async SQLAlchemy engine + session factory. Persistence lives ONLY in
app/repositories/ — nothing outside that layer should import Session directly
in application logic (§2.2 layering: "A route that opens a database session is
a design failure worth marks").
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — inject into repositories only, never into routes/services directly."""
    async with async_session_factory() as session:
        yield session


async def db_is_reachable() -> bool:
    """Used by /ready (§2.2) — cheap connectivity check, not a full query."""
    # TODO(you): implement with `SELECT 1` and a short timeout; catch and return False,
    # never let this raise into the /ready handler.
    raise NotImplementedError
