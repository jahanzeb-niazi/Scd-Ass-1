"""The triage contract: one result model, one interface, one error hierarchy.

Every provider — hosted LLM, local Ollama, keyword rules, CI fake — satisfies
`TriageProvider`. The rest of the system depends only on this module.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.domain import SUMMARY_MAX, Category, Priority


class TriageResult(BaseModel):
    # extra="forbid": a model that adds fields ("override": true, "note": ...)
    # is not following the contract, so the whole answer is rejected.
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=SUMMARY_MAX)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("summary")
    @classmethod
    def _one_line(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("summary must not be blank")
        if "\n" in v or "\r" in v:
            raise ValueError("summary must be a single line")
        return v


@runtime_checkable
class TriageProvider(Protocol):
    name: str  # doubles as the `triaged_by` value, e.g. "llm:gemini"

    def triage(self, text: str, location: str) -> TriageResult: ...


# --------------------------------------------------------------------------
# Errors. The retry policy keys off `retryable`: timeout, 429 and 5xx only.
# --------------------------------------------------------------------------
class TriageError(Exception):
    retryable: bool = False


class ProviderTimeoutError(TriageError):
    retryable = True


class ProviderRateLimitedError(TriageError):
    retryable = True


class ProviderServerError(TriageError):
    retryable = True


class ProviderRequestError(TriageError):
    """4xx other than 429 — the request was wrong and will be wrong again."""


class ProviderUnavailableError(TriageError):
    """Network failure or missing configuration (e.g. no API key)."""


class ProviderOutputError(TriageError):
    """The model answered, but not with something our schema accepts."""


def parse_triage_json(raw: str) -> TriageResult:
    """Validate raw model output against the schema. Never eval, never trust.

    Deliberately strict: we asked for JSON mode, so prose, a markdown code fence,
    an out-of-enum category or a 400-char "one-line" summary is a contract
    violation and the caller falls back to rules.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProviderOutputError(f"not JSON: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise ProviderOutputError("JSON root is not an object")
    try:
        return TriageResult.model_validate(data)
    except ValidationError as exc:
        fields = ",".join(str(e["loc"][0]) for e in exc.errors() if e["loc"])
        raise ProviderOutputError(f"schema violation on: {fields or 'root'}") from exc
