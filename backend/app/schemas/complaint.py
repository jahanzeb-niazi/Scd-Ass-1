"""
Request/response Pydantic models for the complaints API. These are the HTTP
contract — routes/ validates and serializes with these and nothing else.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import Category, Priority, Status


class ComplaintCreate(BaseModel):
    text: str = Field(min_length=10, max_length=2000)
    location: str = Field(min_length=3, max_length=200)
    reporter_contact: str | None = None


class ComplaintOut(BaseModel):
    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: str
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComplaintList(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status: Status


class FieldError(BaseModel):
    field: str
    message: str


class ValidationErrorResponse(BaseModel):
    """Body for 400s per §2.2 API contract: 'field-level error body'."""
    errors: list[FieldError]


# TODO(you): decide whether reporter_contact needs its own validation
# (e.g. loose email/phone shape) — the spec only says "nullable", so this is
# your call; document it if you add constraints.
