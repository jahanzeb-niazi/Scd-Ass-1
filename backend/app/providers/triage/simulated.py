"""SimulatedTriage — the deterministic fake used in CI.

* Seeded: the same (seed, text, location) always gives the same answer.
* No network, no sleep: "timeout" is injected by raising the timeout error,
  not by waiting, so tests never depend on wall-clock time.
* Its output goes through the same `parse_triage_json` validator as a real
  model, so `malformed` mode exercises the real validation path.
"""

from __future__ import annotations

import hashlib
import json
import random

from app.domain import TriagedBy
from app.providers.triage.base import (
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    TriageResult,
    parse_triage_json,
)
from app.providers.triage.rules import RuleBasedTriage

_MALFORMED_OUTPUTS = (
    "Sure! This looks like a water complaint with high priority.",  # prose
    '```json\n{"category": "water", "priority": "high", "summary": "x", "confidence": 1}\n```',
    '{"category": "flooding", "priority": "high", "summary": "x", "confidence": 0.9}',  # not in enum
    '{"category": "water", "priority": "high", "summary": "' + "y" * 400 + '", "confidence": 0.9}',
)


class SimulatedTriage:
    name = TriagedBy.SIMULATED.value

    def __init__(self, seed: int = 42, failure_mode: str = "none", failure_rate: float = 0.0):
        self._seed = seed
        self._mode = failure_mode
        self._rate = failure_rate
        self._rules = RuleBasedTriage()

    def _rng(self, text: str, location: str) -> random.Random:
        digest = hashlib.sha256(f"{self._seed}|{text}|{location}".encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def triage(self, text: str, location: str) -> TriageResult:
        rng = self._rng(text, location)
        if self._mode != "none" and rng.random() < self._rate:
            if self._mode == "timeout":
                raise ProviderTimeoutError("simulated timeout")
            if self._mode == "rate_limit":
                raise ProviderRateLimitedError("simulated 429")
            if self._mode == "bad_request":
                raise ProviderRequestError("simulated 400")
            if self._mode == "malformed":
                return parse_triage_json(rng.choice(_MALFORMED_OUTPUTS))
            raise ProviderServerError("simulated 503")

        base = self._rules.triage(text, location)
        raw = json.dumps(
            {
                "category": base.category.value,
                "priority": base.priority.value,
                "summary": base.summary,
                "confidence": round(0.8 + rng.random() * 0.2, 2),
            }
        )
        return parse_triage_json(raw)
