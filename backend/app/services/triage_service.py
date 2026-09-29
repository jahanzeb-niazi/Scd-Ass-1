"""Triage orchestration: cache → provider (timeout, one jittered retry) → fallback.

This is where the trustworthiness lives. Providers only know how to make one
call and classify its failure; the policy is here, in one place:

  1. content-hash cache in Redis (24 h) — nine neighbours, one inference;
  2. hard wall-clock cap (10 s) on every provider call;
  3. retry once, with jitter, on timeout / 429 / 5xx only — never on 4xx or bad output;
  4. otherwise fall back to RuleBasedTriage and record `rules:fallback`.
     A citizen never sees a 500 because a third party was rate-limited.

Fallback results are NOT cached: a transient outage must not pin a rules-quality
answer onto that text for 24 hours.
"""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import logging
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.domain import TriagedBy
from app.metrics import TRIAGE_CACHE, TRIAGE_FALLBACKS, TRIAGE_LATENCY
from app.providers.cache import Cache, CacheError
from app.providers.triage.base import (
    ProviderTimeoutError,
    TriageError,
    TriageProvider,
    TriageResult,
)
from app.providers.triage.rules import RuleBasedTriage

log = logging.getLogger(__name__)

RECENT_KEY = "triage:recent"
HITS_KEY = "triage:cache:hits"
MISSES_KEY = "triage:cache:misses"
RECENT_MAX = 20


@dataclass(frozen=True)
class TriageOutcome:
    result: TriageResult
    triaged_by: TriagedBy
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error: str | None = None


@dataclass(frozen=True)
class TriageRecord:
    complaint_id: str
    provider: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error: str | None
    at: str


def _normalise(s: str) -> str:
    return " ".join(s.casefold().split())


def content_hash(text: str, location: str) -> str:
    return hashlib.sha256(f"{_normalise(text)}\x1f{_normalise(location)}".encode()).hexdigest()


class TriageService:
    def __init__(
        self,
        provider: TriageProvider,
        cache: Cache,
        *,
        timeout_s: float = 10.0,
        cache_ttl_s: int = 86_400,
        jitter_s: tuple[float, float] = (0.2, 0.8),
        sleep: Callable[[float], None] = time.sleep,
        max_workers: int = 8,
    ) -> None:
        self.provider = provider
        self.fallback = RuleBasedTriage(name=TriagedBy.RULES_FALLBACK.value)
        self._cache = cache
        self._timeout_s = timeout_s
        self._cache_ttl_s = cache_ttl_s
        self._jitter = jitter_s
        self._sleep = sleep
        self._pool = cf.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="triage")
        # Caching a deterministic keyword matcher would only add a Redis round-trip.
        self._cacheable = not isinstance(provider, RuleBasedTriage)

    # ------------------------------------------------------------------ core
    def triage(self, complaint_id: uuid.UUID, text: str, location: str) -> TriageOutcome:
        started = time.perf_counter()
        key = f"triage:v1:{self.provider.name}:{content_hash(text, location)}"

        cached = self._cache_lookup(key) if self._cacheable else None
        if cached is not None:
            return self._finish(cached, started, fallback=False, cache_hit=True)

        error: BaseException | None = None
        for attempt in (1, 2):
            try:
                result = self._call_with_timeout(text, location)
            except TriageError as exc:
                error = exc
                if exc.retryable and attempt == 1:
                    self._sleep(random.uniform(*self._jitter))
                    continue
                break
            except Exception as exc:  # a provider bug must still not become a 500
                error = exc
                break
            else:
                self._cache_store(key, result)
                return self._finish(result, started, fallback=False, cache_hit=False)

        error_class = type(error).__name__ if error else "Unknown"
        log.warning(
            "triage fallback to rules",
            extra={
                "complaint_id": str(complaint_id),
                "provider": self.provider.name,
                "error_class": error_class,
                # e.g. "HTTP 400: API key not valid" — never contains the key.
                "error_detail": str(error)[:240] if error else "",
            },
        )
        TRIAGE_FALLBACKS.labels(provider=self.provider.name, error=error_class).inc()
        result = self.fallback.triage(text, location)
        return self._finish(result, started, fallback=True, cache_hit=False, error=error_class)

    def _call_with_timeout(self, text: str, location: str) -> TriageResult:
        future = self._pool.submit(self.provider.triage, text, location)
        try:
            return future.result(timeout=self._timeout_s)
        except cf.TimeoutError as exc:
            future.cancel()
            raise ProviderTimeoutError(f"exceeded {self._timeout_s}s") from exc

    def _finish(
        self,
        result: TriageResult,
        started: float,
        *,
        fallback: bool,
        cache_hit: bool,
        error: str | None = None,
    ) -> TriageOutcome:
        latency_ms = int((time.perf_counter() - started) * 1000)
        source = TriagedBy.RULES_FALLBACK if fallback else TriagedBy(self.provider.name)
        TRIAGE_LATENCY.labels(provider=source.value).observe(latency_ms / 1000)
        return TriageOutcome(result, source, latency_ms, fallback, cache_hit, error)

    # ----------------------------------------------------------------- cache
    def _cache_lookup(self, key: str) -> TriageResult | None:
        try:
            raw = self._cache.get(key)
            if raw is None:
                self._cache.incr(MISSES_KEY)
                TRIAGE_CACHE.labels(result="miss").inc()
                return None
            self._cache.incr(HITS_KEY)
            TRIAGE_CACHE.labels(result="hit").inc()
            return TriageResult.model_validate_json(raw)
        except CacheError:
            log.warning("triage cache unavailable; calling provider directly")
            return None
        except ValueError:
            return None  # a corrupt entry is just a miss

    def _cache_store(self, key: str, result: TriageResult) -> None:
        try:
            self._cache.set(key, result.model_dump_json(), self._cache_ttl_s)
        except CacheError:
            log.warning("triage cache unavailable; result not cached")

    # --------------------------------------------------------- observability
    def record(self, complaint_id: uuid.UUID, outcome: TriageOutcome) -> None:
        rec = TriageRecord(
            complaint_id=str(complaint_id),
            provider=outcome.triaged_by.value,
            latency_ms=outcome.latency_ms,
            fallback=outcome.fallback,
            cache_hit=outcome.cache_hit,
            error=outcome.error,
            at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        try:
            self._cache.push_capped(RECENT_KEY, json.dumps(asdict(rec)), RECENT_MAX)
        except CacheError:
            log.warning("could not record triage outcome")

    def recent(self) -> list[TriageRecord]:
        try:
            return [
                TriageRecord(**json.loads(r))
                for r in self._cache.list_range(RECENT_KEY, RECENT_MAX)
            ]
        except (CacheError, ValueError, TypeError):
            return []

    def cache_counters(self) -> tuple[int, int]:
        try:
            return self._cache.get_int(HITS_KEY), self._cache.get_int(MISSES_KEY)
        except CacheError:
            return 0, 0

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        close = getattr(self.provider, "close", None)
        if callable(close):
            close()
