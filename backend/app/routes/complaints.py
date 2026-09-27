"""
HTTP layer only — parse, validate, serialize, status codes. No business rules
(§2.2: "A route that opens a database session is a design failure worth marks" —
same applies to embedding logic here instead of in services/).

Endpoints, verbatim from §2.2:
  POST   /api/complaints              -> 201 / 400 / 429
  GET    /api/complaints/{id}         -> 200 / 404
  GET    /api/complaints              -> filter + paginate, returns total
  PATCH  /api/complaints/{id}/status  -> enforce state machine, 409 on invalid
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.db.models import Category, Priority, Status
from app.schemas.complaint import ComplaintCreate, ComplaintList, ComplaintOut, StatusUpdate
from app.services.complaint_service import ComplaintService
from app.services.state_machine import InvalidTransitionError

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


def get_complaint_service() -> ComplaintService:
    # TODO(you): wire real dependency injection (repository + orchestrator built
    # from the configured provider via app/providers/triage/factory.py)
    raise NotImplementedError


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ComplaintOut)
async def create_complaint(
    payload: ComplaintCreate,
    request: Request,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    TODO(you):
      1. Check the distributed rate limiter (app/providers/rate_limiter) keyed
         on request.client.host; on RateLimitExceeded return 429 with a
         Retry-After header (use a Response/JSONResponse, not just raise).
      2. await service.submit_complaint(text=payload.text, location=payload.location,
         reporter_contact=payload.reporter_contact)
      3. Return the created complaint (FastAPI serializes via response_model).
    Pydantic already handles the 400 field-validation case via ComplaintCreate's
    constraints — you don't need to hand-roll that, but confirm the error body
    shape matches what §2.2 calls a "field-level error body".
    """
    raise NotImplementedError


@router.get("/{complaint_id}", response_model=ComplaintOut)
async def get_complaint(
    complaint_id: uuid.UUID,
    service: ComplaintService = Depends(get_complaint_service),
):
    # TODO(you): fetch via service; if None, raise HTTPException(404)
    raise NotImplementedError


@router.get("", response_model=ComplaintList)
async def list_complaints(
    category: Category | None = None,
    priority: Priority | None = None,
    status_filter: Status | None = None,
    page: int = 1,
    page_size: int = 20,
    service: ComplaintService = Depends(get_complaint_service),
):
    # TODO(you): clamp page_size to <=100 (§2.2), call service.list_complaints,
    # wrap into ComplaintList(items=..., total=..., page=..., page_size=...)
    raise NotImplementedError


@router.patch("/{complaint_id}/status", response_model=ComplaintOut)
async def update_status(
    complaint_id: uuid.UUID,
    payload: StatusUpdate,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    TODO(you): call service.update_status; catch InvalidTransitionError and
    return a 409 whose body names the attempted transition, e.g.:

        try:
            return await service.update_status(complaint_id, payload.status)
        except InvalidTransitionError as exc:
            return JSONResponse(
                status_code=409,
                content={"error": f"cannot transition from {exc.current.value} to {exc.attempted.value}"},
            )
    """
    raise NotImplementedError
