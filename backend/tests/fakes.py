"""Fake providers used to drive the triage policy deterministically."""

from __future__ import annotations

import threading

from app.domain import Category, Priority
from app.providers.triage.base import (
    ProviderRequestError,
    ProviderServerError,
    TriageError,
    TriageResult,
    parse_triage_json,
)


class AlwaysRaises:
    """The provider from the spec's must-have test: every call fails."""

    name = "llm:gemini"

    def __init__(self, exc: type[Exception] = ProviderServerError) -> None:
        self.exc = exc
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        raise self.exc("boom")


class ReturnsRaw:
    """Returns fixed raw model text, run through the real validator."""

    name = "llm:gemini"

    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        return parse_triage_json(self.raw)


class Scripted:
    """Raises the scripted errors in order, then succeeds."""

    name = "llm:gemini"

    def __init__(self, *errors: TriageError) -> None:
        self.errors = list(errors)
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return TriageResult(
            category=Category.ROADS, priority=Priority.NORMAL, summary="ok", confidence=0.9
        )


class Blocks:
    """Never answers until released — exercises the wall-clock timeout cap
    without the test itself sleeping."""

    name = "llm:gemini"

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls = 0

    def triage(self, text: str, location: str) -> TriageResult:
        self.calls += 1
        self.release.wait(5)
        raise ProviderRequestError("released")
