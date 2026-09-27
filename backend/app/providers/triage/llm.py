"""LLMTriage — the production path, calling Google Gemini (AI Studio free tier).

Engineering around the model call:
  * structured output requested (responseMimeType + responseSchema), then
    validated again with Pydantic — the model's JSON mode is a hint, not a guarantee;
  * a hard 10 s HTTP timeout here, plus a wall-clock cap in TriageService;
  * HTTP status mapped onto retryable / non-retryable errors (retry policy lives
    in the service, not here);
  * the API key travels in the `x-goog-api-key` header, never in the URL, so it
    cannot leak into an exception message, a log line or a proxy access log;
  * only the redacted complaint body and location are sent (ADR 0004).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.domain import TriagedBy
from app.providers.triage.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TriageResult,
    parse_triage_json,
)
from app.providers.triage.pii import redact
from app.providers.triage.prompt import (
    GEMINI_RESPONSE_SCHEMA,
    SYSTEM_INSTRUCTION,
    build_user_prompt,
)


def raise_for_status(status: int) -> None:
    """Shared HTTP-status → error-class mapping for hosted and local LLMs."""
    if status == 429:
        raise ProviderRateLimitedError("HTTP 429")
    if status >= 500:
        raise ProviderServerError(f"HTTP {status}")
    if status >= 400:
        raise ProviderRequestError(f"HTTP {status}")


class LLMTriage:
    name = TriagedBy.LLM_GEMINI.value

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_s: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self._url = f"{base_url.rstrip('/')}/models/{model}:generateContent"
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s))

    def _payload(self, text: str, location: str) -> dict[str, Any]:
        return {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_user_prompt(redact(text), redact(location))}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 256,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_RESPONSE_SCHEMA,
            },
        }

    def triage(self, text: str, location: str) -> TriageResult:
        if not self._api_key:
            raise ProviderUnavailableError("GEMINI_API_KEY is not set")
        try:
            resp = self._client.post(
                self._url,
                json=self._payload(text, location),
                headers={"x-goog-api-key": self._api_key},
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(type(exc).__name__) from exc

        raise_for_status(resp.status_code)
        try:
            body = resp.json()
            raw = body["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            # Safety blocks and truncated answers land here: no usable candidate.
            raise ProviderOutputError("no candidate text in response") from exc
        return parse_triage_json(raw)

    def close(self) -> None:
        self._client.close()
