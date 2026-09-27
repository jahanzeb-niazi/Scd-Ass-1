"""Composition root: builds every long-lived object once, at startup.

This is the only module that knows about concrete classes from every layer.
Tests build a Container with fakes (fakeredis, a failing provider) instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.providers.cache import RedisCache
from app.providers.rate_limiter import RedisFixedWindowRateLimiter
from app.providers.triage.base import TriageProvider
from app.providers.triage.factory import build_provider
from app.repositories.complaint_repository import ComplaintRepository, StatsSnapshot, ping_database
from app.repositories.database import build_engine, build_session_factory
from app.services.health_service import HealthService, Lifecycle
from app.services.rate_limit_service import RateLimitService
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService

log = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    cache: RedisCache
    triage: TriageService
    stats: StatsService
    rate_limit: RateLimitService
    health: HealthService
    lifecycle: Lifecycle

    @classmethod
    def build(
        cls,
        settings: Settings,
        *,
        redis_client: redis.Redis | None = None,
        provider: TriageProvider | None = None,
        engine: Engine | None = None,
    ) -> Container:
        engine = engine or build_engine(settings)
        session_factory = build_session_factory(engine)
        cache = (
            RedisCache(redis_client)
            if redis_client is not None
            else RedisCache.from_url(settings.redis_url, settings.redis_timeout_s)
        )
        triage = TriageService(
            provider or build_provider(settings),
            cache,
            timeout_s=settings.triage_timeout_s,
            cache_ttl_s=settings.triage_cache_ttl_s,
            jitter_s=(settings.triage_retry_jitter_min_s, settings.triage_retry_jitter_max_s),
        )

        def load_stats() -> StatsSnapshot:
            with session_factory() as session:
                return ComplaintRepository(session).stats()

        lifecycle = Lifecycle()
        return cls(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            cache=cache,
            triage=triage,
            stats=StatsService(cache, load_stats, settings.stats_cache_ttl_s),
            rate_limit=RateLimitService(
                RedisFixedWindowRateLimiter(
                    cache.client, settings.rate_limit_requests, settings.rate_limit_window_s
                ),
                settings.rate_limit_requests,
            ),
            health=HealthService(lambda: ping_database(engine), cache.ping, lifecycle),
            lifecycle=lifecycle,
        )

    def close(self) -> None:
        """Release resources in reverse order of acquisition."""
        self.triage.close()
        self.cache.close()
        self.engine.dispose()
        log.info("resources released: triage pool, redis, db pool")
