"""/api/complaints — HTTP only: parse, validate, call a service, serialise."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.deps import client_ip, get_complaint_service, get_rate_limit_service
from app.domain import Category, Priority, Status
from app.repositories.complaint_repository import ComplaintFilter
from app.routes.errors import RateLimitExceededError
from app.routes.schemas import (
    ComplaintCreate,
    ComplaintCreated,
    ComplaintOut,
    ComplaintPage,
    ErrorOut,
    RateLimitErrorOut,
    StatusUpdate,
    TransitionErrorOut,
    TriageInfo,
    ValidationErrorOut,
)
from app.services.complaint_service import ComplaintService
from app.services.rate_limit_service import RateLimitService

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


def enforce_rate_limit(
    response: Response,
    ip: str = Depends(client_ip),
    limiter: RateLimitService = Depends(get_rate_limit_service),
) -> None:
    decision = limiter.check_submission(ip)
    if not decision.allowed:
        raise RateLimitExceededError(decision.retry_after_s, decision.limit)
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ComplaintCreated,
    dependencies=[Depends(enforce_rate_limit)],
    responses={
        400: {"model": ValidationErrorOut, "description": "Field-level validation errors"},
        429: {"model": RateLimitErrorOut, "description": "Rate limit exceeded; see Retry-After"},
    },
)
def submit_complaint(
    body: ComplaintCreate,
    response: Response,
    svc: ComplaintService = Depends(get_complaint_service),
) -> ComplaintCreated:
    result = svc.submit(body.text, body.location, body.reporter_contact)
    response.headers["Location"] = f"/api/complaints/{result.complaint.id}"
    return ComplaintCreated(
        **ComplaintOut.model_validate(result.complaint).model_dump(),
        triage=TriageInfo(
            confidence=result.confidence, cache_hit=result.cache_hit, fallback=result.fallback
        ),
    )


@router.get(
    "",
    response_model=ComplaintPage,
    responses={400: {"model": ValidationErrorOut}},
)
def list_complaints(
    svc: ComplaintService = Depends(get_complaint_service),
    category: Category | None = None,
    priority: Priority | None = None,
    status_: Annotated[Status | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ComplaintPage:
    result = svc.list(ComplaintFilter(category, priority, status_), page, page_size)
    return ComplaintPage(
        items=[ComplaintOut.model_validate(v) for v in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get(
    "/{complaint_id}",
    response_model=ComplaintOut,
    responses={404: {"model": ErrorOut}, 400: {"model": ValidationErrorOut}},
)
def get_complaint(
    complaint_id: uuid.UUID, svc: ComplaintService = Depends(get_complaint_service)
) -> ComplaintOut:
    return ComplaintOut.model_validate(svc.get(complaint_id))


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    responses={
        400: {"model": ValidationErrorOut},
        404: {"model": ErrorOut},
        409: {"model": TransitionErrorOut, "description": "Transition not allowed"},
    },
)
def change_status(
    complaint_id: uuid.UUID,
    body: StatusUpdate,
    svc: ComplaintService = Depends(get_complaint_service),
) -> ComplaintOut:
    return ComplaintOut.model_validate(svc.change_status(complaint_id, body.status))
