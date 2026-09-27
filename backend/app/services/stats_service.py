"""Aggregate statistics with a Redis read-through cache (TTL 30 s + invalidate on write).

Why both? Invalidation makes our own writes visible immediately; the TTL bounds
staleness for every write path we did not think of (a manual SQL fix, a second
service, a missed invalidation, a failed DEL during a Redis blip).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass

from app.domain import Category, Priority, Status
from app.providers.cache import Cache, CacheError
from app.repositories.complaint_repository import StatsSnapshot

log = logging.getLogger(__name__)

STATS_KEY = "stats:v1"


@dataclass(frozen=True)
class StatsResult:
    stats: StatsSnapshot
    cache_hit: bool


def _complete(snapshot: StatsSnapshot) -> StatsSnapshot:
    """Report every enum value, including zeros, so charts have stable axes."""
    return StatsSnapshot(
        total=snapshot.total,
        by_category={c.value: snapshot.by_category.get(c.value, 0) for c in Category},
        by_priority={p.value: snapshot.by_priority.get(p.value, 0) for p in Priority},
        by_status={s.value: snapshot.by_status.get(s.value, 0) for s in Status},
    )


class StatsService:
    def __init__(self, cache: Cache, load: Callable[[], StatsSnapshot], ttl_s: int = 30) -> None:
        self._cache = cache
        self._load = load
        self._ttl_s = ttl_s

    def get(self) -> StatsResult:
        try:
            raw = self._cache.get(STATS_KEY)
            if raw is not None:
                return StatsResult(StatsSnapshot(**json.loads(raw)), cache_hit=True)
        except CacheError:
            log.warning("stats cache unavailable; reading from database")
        except (ValueError, TypeError):
            pass  # corrupt entry: treat as a miss

        snapshot = _complete(self._load())
        try:
            self._cache.set(STATS_KEY, json.dumps(asdict(snapshot)), self._ttl_s)
        except CacheError:
            log.warning("stats cache unavailable; result not cached")
        return StatsResult(snapshot, cache_hit=False)

    def invalidate(self) -> None:
        try:
            self._cache.delete(STATS_KEY)
        except CacheError:
            # The 30 s TTL is the safety net for exactly this case.
            log.warning("stats cache invalidation failed; TTL will expire it")
