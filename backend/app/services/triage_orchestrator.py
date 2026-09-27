"""
Orchestrates a single triage call: cache lookup -> primary provider -> retry
-> fallback -> cache write. This is the highest-value file in the whole
assignment (rubric section F, 25 marks) — the provider classes themselves are
deliberately dumb; ALL the resilience logic belongs here.

Required behavior, per §2.5 items 2-5:
  1. Hard 10s timeout on every call (settings.triage_timeout_seconds) —
     enforced inside each provider already; this layer just respects it.
  2. Retry exactly once, with jitter, and ONLY on TriageTimeoutError or a
     retryable TriageInvalidOutputError representing a 429/5xx. Never retry
     something representing a 400 (the request was wrong and will be wrong
     again).
  3. On final failure, fall back to RuleBasedTriage. Record
     triaged_by = "rules:fallback" and log exactly one WARNING with the
     complaint id, provider name, and error class (see app/logging_config.py).
  4. Check the content-hash cache BEFORE calling any provider, and populate it
     AFTER a successful (non-fallback) result (§2.5 item 5). Decide yourself
     whether a fallback result should also be cached — document that choice.
  5. Record triage_latency_ms for whichever path actually ran.

The one test that must exist, per the spec's own words ("Write this test if
you write no other"): given a provider that always raises,
POST /api/complaints still returns 201 and triaged_by == "rules:fallback".
See tests/test_triage_fallback.py.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.providers import cache
from app.providers.triage.base import TriageError, TriageProvider
from app.providers.triage.rules import RuleBasedTriage
from app.schemas.triage import TriageResult

logger = logging.getLogger(__name__)


@dataclass
class TriageOutcome:
    result: TriageResult
    triaged_by: str          # e.g. "llm:groq", "rules", "rules:fallback"
    latency_ms: int
    used_fallback: bool


class TriageOrchestrator:
    def __init__(self, primary_provider: TriageProvider) -> None:
        self._primary = primary_provider
        self._fallback = RuleBasedTriage()

    async def run(self, text: str, location: str) -> TriageOutcome:
        """
        TODO(you): implement the full flow described in the module docstring.
        Rough shape (fill in the real logic):

            start = time.perf_counter()

            cached = await cache.get_cached_triage(text, location)
            if cached:
                # TODO: deserialize, return TriageOutcome with triaged_by
                # reflecting that it was a cache hit (decide your own convention)
                ...

            try:
                result = self._call_with_timeout(self._primary, text, location)
            except TriageError as exc:
                if self._is_retryable(exc):
                    try:
                        result = self._call_with_timeout(self._primary, text, location, jitter=True)
                    except TriageError as exc2:
                        return self._fallback_outcome(text, location, start, exc2)
                else:
                    return self._fallback_outcome(text, location, start, exc)

            latency_ms = int((time.perf_counter() - start) * 1000)
            await cache.set_cached_triage(text, location, result.model_dump_json())
            return TriageOutcome(
                result=result,
                triaged_by=self._primary.name,
                latency_ms=latency_ms,
                used_fallback=False,
            )
        """
        raise NotImplementedError

    def _fallback_outcome(self, text: str, location: str, start: float, exc: Exception) -> TriageOutcome:
        """
        TODO(you): call self._fallback.triage(text, location), log ONE warning
        (complaint id isn't known at this layer — pass it in if you restructure,
        or log it one level up in the service that has the complaint id),
        and return a TriageOutcome with triaged_by="rules:fallback",
        used_fallback=True.

        logger.warning(
            "triage_fallback",
            extra={"provider": self._primary.name, "error_class": type(exc).__name__},
        )
        """
        raise NotImplementedError

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """TODO(you): return True only for TriageTimeoutError and rate-limit/5xx
        cases; False for anything representing a 400-equivalent (bad request
        shape that will fail identically on retry)."""
        raise NotImplementedError

    @staticmethod
    def _call_with_timeout(provider: TriageProvider, text: str, location: str, *, jitter: bool = False):
        """TODO(you): add jitter (e.g. random.uniform(0.1, 0.5) sleep) before the
        retry attempt only, not the first attempt. The per-call timeout itself is
        already enforced inside each provider via settings.triage_timeout_seconds."""
        raise NotImplementedError
