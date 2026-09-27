"""Domain vocabulary shared by every layer.

These enums are the single source of truth: the DB enum types, the API schema,
the LLM response schema and the generated TypeScript types all derive from them.
"""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    WATER = "water"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    STREETLIGHTS = "streetlights"
    OTHER = "other"


class Priority(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Status(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class TriagedBy(StrEnum):
    """Which component produced the triage result stored on a complaint."""

    LLM_GEMINI = "llm:gemini"
    # Listed in the spec; kept so a Groq provider can be added without a migration.
    LLM_GROQ = "llm:groq"
    LLM_OLLAMA = "llm:ollama"
    RULES = "rules"
    RULES_FALLBACK = "rules:fallback"
    SIMULATED = "simulated"  # CI-only deterministic fake


# Length rules. Enforced by Pydantic at the API edge AND by CHECK constraints
# in the database (see alembic/versions/0001_initial_schema.py).
TEXT_MIN, TEXT_MAX = 10, 2000
LOCATION_MIN, LOCATION_MAX = 3, 200
CONTACT_MAX = 200
SUMMARY_MAX = 140
