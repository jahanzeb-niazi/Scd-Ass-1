"""Shared fixtures.

Determinism rules for this suite:
  * TRIAGE_PROVIDER is always `simulated` or an injected fake — never the network;
  * Redis is fakeredis, flushed per test;
  * retry jitter is (0, 0), so no test ever sleeps;
  * the database is a real PostgreSQL (TEST_DATABASE_URL), migrated with Alembic
    (down to base, then up to head — which also proves the migration reverses).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import fakeredis
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import Settings
from app.container import Container
from app.main import create_app
from app.providers.triage.base import TriageProvider

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://civicpulse:civicpulse@localhost:5432/civicpulse_test",
)
BACKEND_DIR = Path(__file__).resolve().parents[1]


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": TEST_DATABASE_URL,
        "redis_url": "redis://unused:6379/0",
        "triage_provider": "simulated",
        "triage_retry_jitter_min_s": 0.0,
        "triage_retry_jitter_max_s": 0.0,
        "rate_limit_requests": 1000,
        "trust_proxy_headers": True,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(scope="session")
def migrated_db() -> str:
    url = make_settings().sqlalchemy_url
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable at TEST_DATABASE_URL: {type(exc).__name__}")

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["sqlalchemy_url"] = url
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return url


@pytest.fixture
def clean_db(migrated_db: str) -> Iterator[str]:
    engine = create_engine(migrated_db)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE complaints"))
    engine.dispose()
    yield migrated_db


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    r = fakeredis.FakeRedis(decode_responses=True)
    r.flushall()
    return r


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(clean_db: str, fake_redis: fakeredis.FakeRedis) -> Iterator[ClientFactory]:
    """Build a TestClient with an optional injected provider and setting overrides."""
    containers: list[Container] = []

    def _make(provider: TriageProvider | None = None, **overrides: Any) -> TestClient:
        settings = make_settings(**overrides)
        container = Container.build(settings, redis_client=fake_redis, provider=provider)
        containers.append(container)
        client = TestClient(create_app(settings, container=container))
        client.__enter__()  # run lifespan
        return client

    yield _make
    for c in containers:
        c.triage.close()
        c.engine.dispose()


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


VALID = {
    "text": "Burst water main flooding Street 12 since fajr, water entering ground floors",
    "location": "Street 12, Block 4, Gulshan-e-Iqbal",
}
