"""Complaint persistence. All SQL in the application lives in this package."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain import Category, Priority, Status, TriagedBy
from app.repositories.models import ComplaintRow


@dataclass(frozen=True)
class NewComplaint:
    id: uuid.UUID
    text: str
    location: str
    reporter_contact: str | None
    category: Category
    priority: Priority
    ai_summary: str | None
    triaged_by: TriagedBy
    triage_latency_ms: int
    status: Status = Status.OPEN
    created_at: datetime | None = None  # seed data sets this; normal inserts use now()


@dataclass(frozen=True)
class ComplaintFilter:
    category: Category | None = None
    priority: Priority | None = None
    status: Status | None = None


@dataclass(frozen=True)
class StatsSnapshot:
    total: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_status: dict[str, int]


class ComplaintRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # -- writes ------------------------------------------------------------
    def add(self, c: NewComplaint) -> ComplaintRow:
        row = ComplaintRow(
            id=c.id,
            text=c.text,
            location=c.location,
            reporter_contact=c.reporter_contact,
            category=c.category,
            priority=c.priority,
            status=c.status,
            ai_summary=c.ai_summary,
            triaged_by=c.triaged_by,
            triage_latency_ms=c.triage_latency_ms,
        )
        self._s.add(row)
        self._s.flush()
        self._s.refresh(row)  # pull server defaults (created_at, updated_at)
        return row

    def add_many_ignore_existing(self, items: Iterable[NewComplaint]) -> int:
        """Idempotent bulk insert used by the seed: existing ids are skipped."""
        rows = [
            {
                "id": c.id,
                "text": c.text,
                "location": c.location,
                "reporter_contact": c.reporter_contact,
                "category": c.category,
                "priority": c.priority,
                "status": c.status,
                "ai_summary": c.ai_summary,
                "triaged_by": c.triaged_by,
                "triage_latency_ms": c.triage_latency_ms,
                **(
                    {"created_at": c.created_at, "updated_at": c.created_at} if c.created_at else {}
                ),
            }
            for c in items
        ]
        if not rows:
            return 0
        stmt = (
            insert(ComplaintRow)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[ComplaintRow.id])
            .returning(ComplaintRow.id)
        )
        return len(self._s.execute(stmt).all())

    def get_for_update(self, complaint_id: uuid.UUID) -> ComplaintRow | None:
        """Row-lock so two operators cannot both apply a transition from the same state."""
        stmt = select(ComplaintRow).where(ComplaintRow.id == complaint_id).with_for_update()
        return self._s.execute(stmt).scalar_one_or_none()

    def set_status(self, row: ComplaintRow, status: Status) -> ComplaintRow:
        row.status = status
        self._s.flush()  # updated_at is bumped by the complaints_touch_updated_at trigger
        self._s.refresh(row)
        return row

    def commit(self) -> None:
        self._s.commit()

    def rollback(self) -> None:
        self._s.rollback()

    # -- reads -------------------------------------------------------------
    def get(self, complaint_id: uuid.UUID) -> ComplaintRow | None:
        return self._s.get(ComplaintRow, complaint_id)

    def list(
        self, flt: ComplaintFilter, page: int, page_size: int
    ) -> tuple[list[ComplaintRow], int]:
        conditions = []
        if flt.category is not None:
            conditions.append(ComplaintRow.category == flt.category)
        if flt.priority is not None:
            conditions.append(ComplaintRow.priority == flt.priority)
        if flt.status is not None:
            conditions.append(ComplaintRow.status == flt.status)

        total = self._s.execute(
            select(func.count()).select_from(ComplaintRow).where(*conditions)
        ).scalar_one()
        # Newest first: served by ix_complaints_created_at (backward index scan).
        items = (
            self._s.execute(
                select(ComplaintRow)
                .where(*conditions)
                .order_by(ComplaintRow.created_at.desc(), ComplaintRow.id)
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
            .scalars()
            .all()
        )
        return list(items), int(total)

    def stats(self) -> StatsSnapshot:
        def grouped(col: object) -> dict[str, int]:
            rows = self._s.execute(
                select(col, func.count()).select_from(ComplaintRow).group_by(col)  # type: ignore[call-overload]
            ).all()
            return {str(getattr(k, "value", k)): int(n) for k, n in rows}

        by_status = grouped(ComplaintRow.status)
        return StatsSnapshot(
            total=sum(by_status.values()),
            by_category=grouped(ComplaintRow.category),
            by_priority=grouped(ComplaintRow.priority),
            by_status=by_status,
        )


def ping_database(engine: Engine) -> bool:
    """Readiness check. Lives here because it is SQL."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
