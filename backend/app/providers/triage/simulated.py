"""
Deterministic fake provider for CI (§2.5). No network calls, ever — if this
class imports httpx/openai/redis, that's a bug. Must support configurable
failure injection so tests can exercise the fallback and validation paths
without depending on a real, flaky provider.
"""
from __future__ import annotations

from app.db.models import Category, Priority
from app.providers.triage.base import (
    TriageInvalidOutputError,
    TriageProvider,
    TriageTimeoutError,
)
from app.schemas.triage import TriageResult


class SimulatedTriage(TriageProvider):
    name = "simulated"

    def __init__(
        self,
        *,
        fail_mode: str | None = None,  # None | "timeout" | "invalid_output" | "raise"
    ) -> None:
        self.fail_mode = fail_mode

    def triage(self, text: str, location: str) -> TriageResult:
        if self.fail_mode == "timeout":
            raise TriageTimeoutError("simulated timeout")
        if self.fail_mode == "invalid_output":
            raise TriageInvalidOutputError("simulated malformed output")
        if self.fail_mode == "raise":
            raise RuntimeError("simulated unexpected failure")

        # TODO(you): implement deterministic, seeded logic based on `text`/`location`
        # so tests can assert specific outputs. Keep it simple and predictable —
        # e.g. hash-based or keyword-based selection, NOT random.
        return TriageResult(
            category=Category.OTHER,
            priority=Priority.NORMAL,
            summary=text[:140],
            confidence=1.0,
        )


# TODO(you): the assignment requires "given a provider that always raises,
# POST /api/complaints still returns 201 and triaged_by == 'rules:fallback'"
# (§2.5, "Write this test if you write no other"). Use
# SimulatedTriage(fail_mode="raise") for exactly that test — see
# tests/test_triage_fallback.py.
