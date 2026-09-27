"""
Redis-backed cache provider. Serves TWO purposes deliberately (§2.4):
  1. Read-through cache for /api/stats (TTL 30s, invalidate on write)
  2. Content-hash cache for triage results (TTL 24h, §2.5 item 5)
Both go through this one class so the "infrastructure is a capability, not a
single-purpose box" point is visible in one place.
"""
from __future__ import annotations

import hashlib
import json

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


# --- Stats cache (§2.4 Job 1) ---

STATS_CACHE_KEY = "stats:aggregate"


async def get_cached_stats() -> tuple[str | None, bool]:
    """Returns (json_string_or_None, was_hit)."""
    client = get_redis()
    value = await client.get(STATS_CACHE_KEY)
    return value, value is not None


async def set_cached_stats(payload: dict) -> None:
    client = get_redis()
    await client.set(STATS_CACHE_KEY, json.dumps(payload), ex=settings.stats_cache_ttl_seconds)


async def invalidate_stats_cache() -> None:
    """Call this on every complaint write — do NOT rely on TTL alone (§2.4:
    'Invalidate on write, so a newly submitted complaint appears in the stats
    immediately rather than up to 30 seconds later')."""
    client = get_redis()
    await client.delete(STATS_CACHE_KEY)


# --- Triage content-hash cache (§2.5 item 5) ---

def _content_hash(text: str, location: str) -> str:
    return hashlib.sha256(f"{text}|{location}".encode()).hexdigest()


async def get_cached_triage(text: str, location: str) -> str | None:
    client = get_redis()
    return await client.get(f"triage:{_content_hash(text, location)}")


async def set_cached_triage(text: str, location: str, result_json: str) -> None:
    client = get_redis()
    key = f"triage:{_content_hash(text, location)}"
    await client.set(key, result_json, ex=settings.triage_cache_ttl_seconds)


# TODO(you): track a hit/miss counter for the triage cache so you can report a
# measured hit rate (§2.5 item 5, rubric item F: "measured, reported hit rate").
# A simple Redis INCR on hit and on miss, read back for the report, is enough.
