"""Why is triage not using the LLM?  Run inside the backend container:

    docker compose exec backend python -m app.diagnose

Prints the effective triage settings (never the key itself), then makes ONE
real call through the configured provider and reports exactly what happened.
Read-only: nothing is written to the database or the cache.
"""

from __future__ import annotations

import socket
import sys
import time
from urllib.parse import urlparse

from app.config import get_settings
from app.providers.triage.base import TriageError
from app.providers.triage.factory import build_provider

SAMPLE = (
    "Burst water main flooding Street 12 since fajr, water entering ground floors",
    "Street 12",
)


def main() -> int:
    s = get_settings()
    key = s.gemini_api_key.get_secret_value()
    print("TRIAGE_PROVIDER   :", s.triage_provider)
    if s.triage_provider == "llm":
        print("GEMINI_MODEL      :", s.gemini_model)
        print(
            "GEMINI_API_KEY    :",
            "EMPTY" if not key else f"set, {len(key)} chars, starts {key[:4]}…",
        )
        if key and (key != key.strip() or key[:1] in "\"'" or key[-1:] in "\"'"):
            print("  !! key has surrounding spaces or quotes — remove them in .env")
        if key and not key.startswith("AIza"):
            print(
                "  !! AI Studio keys normally start with 'AIza' — check you copied the right value"
            )
        host = urlparse(s.gemini_base_url).hostname or ""
    elif s.triage_provider == "ollama":
        print("OLLAMA_URL        :", s.ollama_url, " model:", s.ollama_model)
        host = urlparse(s.ollama_url).hostname or ""
    else:
        print(
            f"\nTRIAGE_PROVIDER={s.triage_provider} never calls an LLM. Set TRIAGE_PROVIDER=llm in .env,"
        )
        print("then: docker compose up -d --force-recreate backend")
        return 1

    try:
        print("DNS               :", host, "→", socket.gethostbyname(host))
    except OSError as exc:
        print("DNS               :", host, "FAILED —", exc)

    provider = build_provider(s)
    print(f"\nCalling {provider.name} once (timeout {s.triage_timeout_s}s)…")
    started = time.perf_counter()
    try:
        result = provider.triage(*SAMPLE)
    except TriageError as exc:
        ms = int((time.perf_counter() - started) * 1000)
        print(f"FAILED after {ms} ms: {type(exc).__name__}: {exc}")
        return 1
    ms = int((time.perf_counter() - started) * 1000)
    print(f"OK in {ms} ms → {result.model_dump()}")
    print("\nThe provider works. New complaints should show triaged_by =", provider.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
