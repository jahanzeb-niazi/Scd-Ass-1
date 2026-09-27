"""
All SQL lives here, and nowhere else (§2.2 layering). Services call this
repository; this repository never contains business rules (e.g. it should not
decide whether a status transition is valid — that's app/services/state_machine.py).
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Complaint, Category, Priority, Status


class ComplaintRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, complaint: Complaint) -> Complaint:
        # TODO(you): self._session.add(complaint); await self._session.commit();
        # await self._session.refresh(complaint); return complaint
        raise NotImplementedError

    async def get_by_id(self, complaint_id: uuid.UUID) -> Complaint | None:
        # TODO(you): implement with select(Complaint).where(Complaint.id == complaint_id)
        raise NotImplementedError

    async def list_filtered(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Complaint], int]:
        """Returns (items, total_count). page_size must be clamped to <=100 by the
        caller (route/service), per the API contract (§2.2).

        TODO(you): build the filtered query, apply .offset()/.limit(), and run a
        separate func.count() query for `total`. This is also where the
        (status, priority) and created_at indexes (§2.3) should actually get used —
        make sure your ORDER BY matches the created_at index if you sort by it.
        """
        raise NotImplementedError

    async def update_status(self, complaint_id: uuid.UUID, new_status: Status) -> Complaint | None:
        # TODO(you): fetch, mutate .status, commit, return updated row (or None if not found).
        # State-machine legality is validated by the caller BEFORE this is invoked —
        # this method should not re-implement the transition table.
        raise NotImplementedError

    async def get_stats(self) -> dict:
        """Aggregate counts by category and priority (§2.2 GET /api/stats).

        TODO(you): implement with GROUP BY category / GROUP BY priority queries,
        e.g.:
            select(Complaint.category, func.count()).group_by(Complaint.category)
        Shape the return value to match whatever your StatsService/route expects.
        """
        raise NotImplementedError
