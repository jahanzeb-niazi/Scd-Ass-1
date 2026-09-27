"""Redis job 2: a distributed fixed-window rate limiter.

The counter lives in Redis, not in a process-local dict, because with N backend
replicas an in-process limiter permits N times the traffic. Every pod shares the
same key, so the limit is per client IP across the whole deployment.

Algorithm (atomic in one MULTI/EXEC round-trip):
    key = rl:{scope}:{ip}:{window_index}
    INCR key            -> n
    EXPIRE key W NX     -> first request of the window sets the TTL (cleanup)
    allowed = n <= limit;  Retry-After = seconds until the window boundary
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import redis


class RateLimiterUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_s: int


class RateLimiter(Protocol):
    def hit(self, scope: str, client_id: str) -> RateLimitDecision: ...


class RedisFixedWindowRateLimiter:
    def __init__(self, client: redis.Redis, limit: int, window_s: int) -> None:
        self._r = client
        self.limit = limit
        self.window_s = window_s

    def hit(self, scope: str, client_id: str) -> RateLimitDecision:
        now = time.time()
        window = int(now) // self.window_s
        key = f"rl:{scope}:{client_id}:{window}"
        pipe = self._r.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, self.window_s, nx=True)  # garbage-collect old windows
        try:
            count, _ = pipe.execute()
        except redis.RedisError as exc:
            raise RateLimiterUnavailableError(type(exc).__name__) from exc
        count = int(count)
        # Seconds until this window ends — the honest Retry-After.
        retry_after = max(1, int((window + 1) * self.window_s - now + 0.999))
        return RateLimitDecision(
            allowed=count <= self.limit,
            limit=self.limit,
            remaining=max(self.limit - count, 0),
            retry_after_s=retry_after,
        )
