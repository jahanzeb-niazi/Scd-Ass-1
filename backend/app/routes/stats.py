"""/api/stats and /api/meta/providers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.container import Container
from app.deps import get_container, get_stats_service, get_triage_service
from app.routes.schemas import ProvidersOut, StatsOut, TriageCacheOut, TriageOutcomeOut
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService

router = APIRouter(prefix="/api", tags=["stats"])


@router.get(
    "/stats",
    response_model=StatsOut,
    responses={
        200: {"headers": {"X-Cache": {"description": "HIT or MISS", "schema": {"type": "string"}}}}
    },
)
def get_stats(response: Response, svc: StatsService = Depends(get_stats_service)) -> StatsOut:
    result = svc.get()
    response.headers["X-Cache"] = "HIT" if result.cache_hit else "MISS"
    response.headers["Cache-Control"] = "no-store"  # browsers must not add a second cache layer
    s = result.stats
    return StatsOut.model_validate(
        {
            "total": s.total,
            "by_category": s.by_category,
            "by_priority": s.by_priority,
            "by_status": s.by_status,
        }
    )


@router.get("/meta/providers", response_model=ProvidersOut, tags=["meta"])
def get_providers(
    triage: TriageService = Depends(get_triage_service),
    c: Container = Depends(get_container),
) -> ProvidersOut:
    hits, misses = triage.cache_counters()
    lookups = hits + misses
    return ProvidersOut(
        active=triage.provider.name,
        configured=c.settings.triage_provider,
        fallback=triage.fallback.name,
        model=getattr(triage.provider, "model", None),
        timeout_s=c.settings.triage_timeout_s,
        cache=TriageCacheOut(
            hits=hits, misses=misses, hit_rate=round(hits / lookups, 4) if lookups else None
        ),
        recent=[TriageOutcomeOut.model_validate(r, from_attributes=True) for r in triage.recent()],
    )
