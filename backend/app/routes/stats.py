"""
GET /api/stats — aggregates, Redis-cached, TTL 30s, X-Cache: HIT|MISS (§2.2).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.services.complaint_service import ComplaintService
from app.routes.complaints import get_complaint_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(
    response: Response,
    service: ComplaintService = Depends(get_complaint_service),
):
    """
    TODO(you):
        value, was_hit = await service.get_stats()
        response.headers["X-Cache"] = "HIT" if was_hit else "MISS"
        return value
    """
    raise NotImplementedError
