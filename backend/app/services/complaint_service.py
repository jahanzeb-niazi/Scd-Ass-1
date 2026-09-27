"""
Business rules for the complaint lifecycle. Routes call this; this calls
the repository and the triage orchestrator. No SQL here, no HTTP concerns here.
"""
from __future__ import annotations

import uuid

from app.db.models import Category, Priority, Status
from app.repositories.complaint_repository import ComplaintRepository
from app.services.state_machine import InvalidTransitionError, validate_transition
from app.services.triage_orchestrator import TriageOrchestrator


class ComplaintService:
    def __init__(self, repository: ComplaintRepository, orchestrator: TriageOrchestrator) -> None:
        self._repo = repository
        self._orchestrator = orchestrator

    async def submit_complaint(self, *, text: str, location: str, reporter_contact: str | None):
        """
        TODO(you): 
          1. await self._orchestrator.run(text, location) to get a TriageOutcome
          2. build a Complaint ORM row with category/priority/ai_summary/triaged_by/
             triage_latency_ms from that outcome, status=Status.OPEN
          3. await self._repo.create(...)
          4. invalidate the stats cache (app/providers/cache.invalidate_stats_cache) —
             §2.4: "Invalidate on write, so a newly submitted complaint appears in
             the stats immediately"
          5. return the created Complaint
        """
        raise NotImplementedError

    async def get_complaint(self, complaint_id: uuid.UUID):
        # TODO(you): return self._repo.get_by_id(complaint_id); route handles the 404
        raise NotImplementedError

    async def list_complaints(
        self,
        *,
        category: Category | None,
        priority: Priority | None,
        status: Status | None,
        page: int,
        page_size: int,
    ):
        # TODO(you): clamp page_size to <=100 here (belt-and-suspenders with the
        # route's own validation), then delegate to self._repo.list_filtered(...)
        raise NotImplementedError

    async def update_status(self, complaint_id: uuid.UUID, new_status: Status):
        """
        TODO(you):
          1. fetch current complaint via self._repo.get_by_id (404 if missing —
             let the route translate a None/lookup failure into 404)
          2. validate_transition(current.status, new_status) — let
             InvalidTransitionError propagate; the route catches it and returns
             409 naming the attempted transition (§2.2)
          3. await self._repo.update_status(complaint_id, new_status)
        """
        raise NotImplementedError

    async def get_stats(self):
        """
        TODO(you): read-through cache pattern (§2.4 Job 1):
          1. cached, hit = await cache.get_cached_stats()
          2. if hit: return (parsed cached value, was_cache_hit=True)
          3. else: value = await self._repo.get_stats(); await cache.set_cached_stats(value);
             return (value, was_cache_hit=False)
        The route uses was_cache_hit to set the X-Cache header.
        """
        raise NotImplementedError
