"""
Deterministic keyword-based fallback. Must NEVER fail — this is what the
orchestrator falls back to when the LLM path is unavailable, so if this
raises, a citizen sees a 500 (which the spec explicitly forbids, §2.5 item 4).
"""
from __future__ import annotations

from app.db.models import Category, Priority
from app.providers.triage.base import TriageProvider
from app.schemas.triage import TriageResult

# TODO(you): build out real keyword -> category mappings, e.g.
# KEYWORD_CATEGORY_MAP = {
#     "water": Category.WATER, "burst": Category.WATER, "leak": Category.WATER,
#     "electricity": Category.ELECTRICITY, "power": Category.ELECTRICITY,
#     "sewage": Category.SANITATION, "garbage": Category.SANITATION,
#     "road": Category.ROADS, "pothole": Category.ROADS,
#     "streetlight": Category.STREETLIGHTS, "light": Category.STREETLIGHTS,
# }
#
# TODO(you): build out urgency keyword logic for Priority, e.g. words like
# "flooding", "fire", "danger" -> Priority.HIGH.

KEYWORD_CATEGORY_MAP: dict[str, Category] = {}
URGENT_KEYWORDS: set[str] = set()


class RuleBasedTriage(TriageProvider):
    name = "rules"

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()

        category = Category.OTHER
        # TODO(you): iterate KEYWORD_CATEGORY_MAP and pick first/best match

        priority = Priority.NORMAL
        # TODO(you): check URGENT_KEYWORDS -> Priority.HIGH

        summary = text.strip()[:140]  # TODO(you): smarter one-line summarization if desired

        return TriageResult(category=category, priority=priority, summary=summary, confidence=0.5)
