"""
Distributed rate limiter on POST /api/complaints, keyed by client IP (§2.4
Job 2). MUST be in Redis, not an in-process dict — the spec is explicit that
an in-process limiter breaks the moment the HPA scales you to N pods, since
each pod would then allow N times the intended rate.
"""
from __future__ import annotations

from app.config import settings
from app.providers.cache import get_redis


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limit exceeded, retry after {retry_after_seconds}s")


async def check_rate_limit(client_ip: str) -> None:
    """Raises RateLimitExceeded if the caller is over budget.

    TODO(you): implement as a fixed-window or token-bucket counter in Redis.
    Fixed-window sketch:
        key = f"ratelimit:{client_ip}:{current_window_start}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.rate_limit_window_seconds)
        if count > settings.rate_limit_requests:
            raise RateLimitExceeded(retry_after_seconds=<seconds to next window>)

    Wire the raised exception in app/routes/complaints.py to return 429 with
    a Retry-After header (§2.2 API contract).
    """
    raise NotImplementedError
