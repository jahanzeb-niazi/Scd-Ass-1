"""Select the triage provider from TRIAGE_PROVIDER. The only place that knows
which concrete classes exist — everything else sees `TriageProvider`."""

from __future__ import annotations

import logging

from app.config import Settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage

log = logging.getLogger(__name__)


def build_provider(settings: Settings) -> TriageProvider:
    choice = settings.triage_provider
    if choice == "llm":
        key = settings.gemini_api_key.get_secret_value()
        if not key:
            # Deliberately not fatal: a clean clone with no key still runs, and
            # every complaint is triaged by rules:fallback (visible in /api/meta/providers).
            log.warning(
                "TRIAGE_PROVIDER=llm but GEMINI_API_KEY is empty; every triage will fall back",
                extra={"provider": LLMTriage.name},
            )
        return LLMTriage(
            api_key=key,
            model=settings.gemini_model,
            base_url=settings.gemini_base_url,
            timeout_s=settings.triage_timeout_s,
        )
    if choice == "ollama":
        return OllamaTriage(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
            timeout_s=settings.triage_timeout_s,
        )
    if choice == "simulated":
        return SimulatedTriage(
            seed=settings.simulated_seed,
            failure_mode=settings.simulated_failure_mode,
            failure_rate=settings.simulated_failure_rate,
        )
    return RuleBasedTriage()
