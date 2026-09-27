"""
Selects a TriageProvider implementation by TRIAGE_PROVIDER env var (§2.5).
This is the ONLY place that should decide which concrete provider class to
instantiate — services/routes should depend on the TriageProvider Protocol,
never import a concrete provider directly.
"""
from __future__ import annotations

from app.config import settings
from app.providers.triage.base import TriageProvider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage


def get_triage_provider() -> TriageProvider:
    match settings.triage_provider:
        case "llm":
            return LLMTriage()
        case "ollama":
            return OllamaTriage()
        case "rules":
            return RuleBasedTriage()
        case "simulated":
            return SimulatedTriage()
        case other:
            raise ValueError(f"Unknown TRIAGE_PROVIDER: {other!r}")


# TODO(you): the fallback provider used by the orchestrator on failure should
# always be RuleBasedTriage() regardless of TRIAGE_PROVIDER — wire that
# explicitly in app/services/triage_orchestrator.py, don't route it through
# this factory.
