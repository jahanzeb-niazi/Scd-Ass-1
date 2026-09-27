"""
Fully offline triage path — calls a local Ollama container (§2.5). Same
interface and same non-responsibilities as llm.py: no retry/fallback here,
that's the orchestrator's job.
"""
from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from app.config import settings
from app.providers.triage.base import (
    TriageInvalidOutputError,
    TriageProvider,
    TriageTimeoutError,
)
from app.schemas.triage import TriageResult
from app.providers.triage.llm import SYSTEM_PROMPT  # reuse the same injection-guardrail prompt


class OllamaTriage(TriageProvider):
    name = "llm:ollama"

    def triage(self, text: str, location: str) -> TriageResult:
        prompt = f"{SYSTEM_PROMPT}\n\n<complaint_text>{text}</complaint_text>\n<location>{location}</location>"

        try:
            resp = httpx.post(
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=settings.triage_timeout_seconds,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TriageTimeoutError(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise TriageInvalidOutputError(f"ollama request failed: {exc}") from exc

        raw = resp.json().get("response", "")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TriageInvalidOutputError(f"non-JSON response: {exc}") from exc

        try:
            return TriageResult.model_validate(data)
        except ValidationError as exc:
            raise TriageInvalidOutputError(f"schema validation failed: {exc}") from exc


# TODO(you): §2.5 notes Ollama is "slower on CPU and noticeably worse at
# classification" — measure this yourself and write the comparison into
# docs/adr/0001-provider-interface.md as part of the buy-vs-host trade-off.
