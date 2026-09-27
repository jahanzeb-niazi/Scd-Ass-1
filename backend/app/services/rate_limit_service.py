"""Rate-limit policy for complaint submission, on top of the Redis limiter."""

from __future__ import annotations

import logging

from app.metrics import RATE_LIMITED
from app.providers.rate_limiter import RateLimitDecision, RateLimiter, RateLimiterUnavailableError

log = logging.getLogger(__name__)


class RateLimitService:
    def __init__(self, limiter: RateLimiter, limit: int) -> None:
        self._limiter = limiter
        self._limit = limit

    def check_submission(self, client_ip: str) -> RateLimitDecision:
        try:
            decision = self._limiter.hit("complaints:post", client_ip)
        except RateLimiterUnavailableError:
            # Fail open: if Redis is down, /ready already reports it and the pod
            # leaves the Service; refusing citizens here would turn a cache
            # outage into an intake outage. The LLM quota is still protected by
            # the fallback path.
            log.warning(
                "rate limiter unavailable; allowing request", extra={"client_ip": client_ip}
            )
            return RateLimitDecision(True, self._limit, self._limit, 0)
        if not decision.allowed:
            RATE_LIMITED.inc()
            log.info("rate limit exceeded", extra={"client_ip": client_ip})
        return decision
