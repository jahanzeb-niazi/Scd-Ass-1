"""/health (liveness), /ready (readiness), /metrics (Prometheus)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.deps import get_health_service
from app.routes.schemas import HealthOut, ReadinessOut
from app.services.health_service import HealthService

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    # Liveness: the process can serve a request. Deliberately touches no
    # dependency — a slow database must not make Kubernetes restart this pod.
    return HealthOut(status="ok")


@router.get("/ready", response_model=ReadinessOut, responses={503: {"model": ReadinessOut}})
def ready(svc: HealthService = Depends(get_health_service)) -> JSONResponse:
    r = svc.readiness()
    body = ReadinessOut(
        status="ready" if r.ready else "unavailable", checks=r.checks, failed=r.failed
    )
    return JSONResponse(status_code=200 if r.ready else 503, content=body.model_dump())


@router.get("/metrics", response_class=Response, include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
