"""
The contract every TriageProvider must return. Copied verbatim from the
assignment spec §2.5 — do not loosen these constraints; the whole point of
"structured output, enforced" (§2.5 item 1) is that this model is what you
validate LLM output against, and reject anything that doesn't fit.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models import Category, Priority


class TriageResult(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(max_length=140)
    confidence: float = Field(ge=0.0, le=1.0)
