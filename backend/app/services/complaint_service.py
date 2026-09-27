"""Complaint use-cases: submit (validate → triage → persist), read, list, transition."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain import Category, Priority, Status, TriagedBy
from app.repositories.complaint_repository import ComplaintFilter, ComplaintRepository, NewComplaint
from app.repositories.models import ComplaintRow
from app.services.errors import InvalidTransitionError, NotFoundError
from app.services.state_machine import allowed_from, can_transition
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


@dataclass(frozen=True)
class ComplaintView:
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
    allowed_transitions: list[Status]

    @classmethod
    def from_row(cls, row: ComplaintRow) -> ComplaintView:
        return cls(
            id=row.id,
            text=row.text,
            location=row.location,
            reporter_contact=row.reporter_contact,
            category=row.category,
            priority=row.priority,
            status=row.status,
            ai_summary=row.ai_summary,
            triaged_by=row.triaged_by,
            triage_latency_ms=row.triage_latency_ms,
            created_at=row.created_at,
            updated_at=row.updated_at,
            allowed_transitions=allowed_from(row.status),
        )


@dataclass(frozen=True)
class SubmitResult:
    complaint: ComplaintView
    confidence: float
    cache_hit: bool
    fallback: bool


@dataclass(frozen=True)
class Page:
    items: list[ComplaintView]
    total: int
    page: int
    page_size: int


class ComplaintService:
    def __init__(
        self, repo: ComplaintRepository, triage: TriageService, stats: StatsService
    ) -> None:
        self._repo = repo
        self._triage = triage
        self._stats = stats

    def submit(self, text: str, location: str, reporter_contact: str | None) -> SubmitResult:
        # The id is generated before triage so a fallback WARNING can name it.
        complaint_id = uuid.uuid4()
        outcome = self._triage.triage(complaint_id, text, location)
        row = self._repo.add(
            NewComplaint(
                id=complaint_id,
                text=text,
                location=location,
                reporter_contact=reporter_contact,
                category=outcome.result.category,
                priority=outcome.result.priority,
                ai_summary=outcome.result.summary,
                triaged_by=outcome.triaged_by,
                triage_latency_ms=outcome.latency_ms,
            )
        )
        self._repo.commit()
        # Invalidate only after commit, so no reader can re-cache pre-commit stats.
        self._stats.invalidate()
        self._triage.record(complaint_id, outcome)
        return SubmitResult(
            complaint=ComplaintView.from_row(row),
            confidence=outcome.result.confidence,
            cache_hit=outcome.cache_hit,
            fallback=outcome.fallback,
        )

    def get(self, complaint_id: uuid.UUID) -> ComplaintView:
        row = self._repo.get(complaint_id)
        if row is None:
            raise NotFoundError(complaint_id)
        return ComplaintView.from_row(row)

    def list(self, flt: ComplaintFilter, page: int, page_size: int) -> Page:
        rows, total = self._repo.list(flt, page, page_size)
        return Page([ComplaintView.from_row(r) for r in rows], total, page, page_size)

    def change_status(self, complaint_id: uuid.UUID, target: Status) -> ComplaintView:
        row = self._repo.get_for_update(complaint_id)
        if row is None:
            self._repo.rollback()
            raise NotFoundError(complaint_id)
        current = row.status
        if not can_transition(current, target):
            self._repo.rollback()
            raise InvalidTransitionError(current, target, allowed_from(current))
        row = self._repo.set_status(row, target)
        self._repo.commit()
        self._stats.invalidate()
        return ComplaintView.from_row(row)
