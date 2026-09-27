"""FastAPI dependency providers.

Routes receive *services*, never sessions. The per-request DB session is opened
and closed here, so no route handler ever touches persistence directly.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request

from app.container import Container
from app.repositories.complaint_repository import ComplaintRepository
from app.services.complaint_service import ComplaintService
from app.services.health_service import HealthService
from app.services.rate_limit_service import RateLimitService
from app.services.stats_service import StatsService
from app.services.triage_service import TriageService


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def _repository(c: Container = Depends(get_container)) -> Iterator[ComplaintRepository]:
    session = c.session_factory()
    try:
        yield ComplaintRepository(session)
    finally:
        session.close()  # rolls back anything a service did not commit


def get_complaint_service(
    repo: ComplaintRepository = Depends(_repository),
    c: Container = Depends(get_container),
) -> ComplaintService:
    return ComplaintService(repo, c.triage, c.stats)


def get_stats_service(c: Container = Depends(get_container)) -> StatsService:
    return c.stats


def get_triage_service(c: Container = Depends(get_container)) -> TriageService:
    return c.triage


def get_rate_limit_service(c: Container = Depends(get_container)) -> RateLimitService:
    return c.rate_limit


def get_health_service(c: Container = Depends(get_container)) -> HealthService:
    return c.health


def client_ip(request: Request, c: Container = Depends(get_container)) -> str:
    """Client IP for rate limiting.

    Behind exactly one trusted proxy (nginx in Compose, the Ingress controller
    in k8s) the right-most X-Forwarded-For entry is the address that proxy saw.
    Left-most entries are client-supplied and trivially spoofable.
    """
    if c.settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[-1].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"
