"""HTTP request/response schemas. These define the OpenAPI document that the
frontend's TypeScript client is generated from."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import (
    CONTACT_MAX,
    LOCATION_MAX,
    LOCATION_MIN,
    TEXT_MAX,
    TEXT_MIN,
    Category,
    Priority,
    Status,
    TriagedBy,
)


# ---------------------------------------------------------------- requests
class ComplaintCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "text": "Burst water main flooding Street 12 since fajr, water entering ground floors",
                    "location": "Street 12, Block 4, Gulshan-e-Iqbal, Karachi",
                    "reporter_contact": None,
                }
            ]
        },
    )

    text: str = Field(min_length=TEXT_MIN, max_length=TEXT_MAX, description="What is wrong")
    location: str = Field(min_length=LOCATION_MIN, max_length=LOCATION_MAX)
    reporter_contact: str | None = Field(default=None, max_length=CONTACT_MAX)

    @field_validator("reporter_contact")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        return v or None


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


# --------------------------------------------------------------- responses
class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    status: Status
    ai_summary: str | None
    triaged_by: TriagedBy
    triage_latency_ms: int
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[Status] = Field(
        description="Statuses this complaint may move to next, decided by the server's state machine"
    )


class TriageInfo(BaseModel):
    confidence: float
    cache_hit: bool
    fallback: bool


class ComplaintCreated(ComplaintOut):
    triage: TriageInfo


class ComplaintPage(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class StatsOut(BaseModel):
    total: int
    by_category: dict[Category, int]
    by_priority: dict[Priority, int]
    by_status: dict[Status, int]


class TriageOutcomeOut(BaseModel):
    complaint_id: str
    provider: str
    latency_ms: int
    fallback: bool
    cache_hit: bool
    error: str | None
    at: str


class TriageCacheOut(BaseModel):
    hits: int
    misses: int
    hit_rate: float | None


class ProvidersOut(BaseModel):
    active: str = Field(description="triaged_by value the active provider writes, e.g. llm:gemini")
    configured: str = Field(description="TRIAGE_PROVIDER setting")
    fallback: str
    model: str | None
    timeout_s: float
    cache: TriageCacheOut
    recent: list[TriageOutcomeOut]


class HealthOut(BaseModel):
    status: str


class ReadinessOut(BaseModel):
    status: str
    checks: dict[str, str]
    failed: list[str]


# ------------------------------------------------------------------ errors
class ErrorOut(BaseModel):
    detail: str
    request_id: str | None = None


class FieldErrorOut(BaseModel):
    field: str
    message: str
    type: str


class ValidationErrorOut(BaseModel):
    detail: str
    errors: list[FieldErrorOut]
    request_id: str | None = None


class TransitionErrorOut(BaseModel):
    detail: str
    current: Status
    attempted: Status
    allowed: list[Status]
    request_id: str | None = None


class RateLimitErrorOut(BaseModel):
    detail: str
    retry_after_s: int
    request_id: str | None = None
