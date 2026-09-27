"""
The provider interface, copied verbatim from the assignment spec §2.5.
Every implementation (simulated, rules, llm, ollama) must satisfy this
Protocol. This is the single most important abstraction in the assignment —
implement your actual triage logic in the concrete classes, not here.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas.triage import TriageResult


class TriageProvider(Protocol):
    name: str

    def triage(self, text: str, location: str) -> TriageResult: ...


class TriageError(Exception):
    """Raised by a provider on failure (timeout, bad response, rate limited, etc).
    The orchestrator (app/services/triage_orchestrator.py) catches this and
    decides whether to retry or fall back — providers themselves should not
    implement retry/fallback logic."""


class TriageTimeoutError(TriageError):
    pass


class TriageInvalidOutputError(TriageError):
    """Raised when a provider's raw response fails validation against TriageResult."""
