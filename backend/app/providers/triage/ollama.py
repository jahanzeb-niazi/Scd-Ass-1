"""OllamaTriage — fully offline path. Same interface, a container in Compose.

No key, no rate limit, and no PII leaves the machine, so no redaction is needed.
Slower on CPU and weaker at classification: the buy-vs-host trade-off, measured.
"""

from __future__ import annotations

import httpx

from app.domain import TriagedBy
from app.providers.triage.base import (
    ProviderOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TriageResult,
    parse_triage_json,
)
from app.providers.triage.llm import raise_for_status
from app.providers.triage.prompt import RESPONSE_JSON_SCHEMA, SYSTEM_INSTRUCTION, build_user_prompt


class OllamaTriage:
    name = TriagedBy.LLM_OLLAMA.value

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._client = client or httpx.Client(timeout=httpx.Timeout(timeout_s))

    def triage(self, text: str, location: str) -> TriageResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": RESPONSE_JSON_SCHEMA,  # Ollama structured outputs
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": build_user_prompt(text, location)},
            ],
        }
        try:
            resp = self._client.post(self._url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(type(exc).__name__) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(type(exc).__name__) from exc

        raise_for_status(resp.status_code)
        try:
            raw = resp.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderOutputError("no message content in response") from exc
        return parse_triage_json(raw)

    def close(self) -> None:
        self._client.close()
