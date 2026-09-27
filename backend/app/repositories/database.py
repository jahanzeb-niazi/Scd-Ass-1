"""Engine and session factory. Built once at startup, disposed on shutdown."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
        pool_pre_ping=True,
        pool_timeout=5,
        # Pin the session to UTC so timestamptz values always serialise as +00:00,
        # whatever timezone the database host happens to be configured with.
        connect_args={
            "connect_timeout": settings.db_connect_timeout_s,
            "options": "-c timezone=UTC",
        },
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
