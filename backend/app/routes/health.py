"""
/health, /ready, /metrics (§2.2). The liveness/readiness split is deliberately
strict — get this wrong and a slow database turns into a restart loop across
your whole deployment (§2.2 explains why explicitly).
"""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.db.session import db_is_reachable
from app.providers.cache import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Liveness. Process is alive. MUST NOT touch the database (§2.2)."""
    return {"status": "alive"}


@router.get("/ready")
async def ready(response: Response):
    """
    Readiness. 200 only if Postgres AND Redis are both reachable; 503 naming
    the failed dependency (§2.2).

    TODO(you):
        db_ok = await db_is_reachable()
        try:
            redis_ok = await get_redis().ping()
        except Exception:
            redis_ok = False

        if db_ok and redis_ok:
            return {"status": "ready"}

        response.status_code = 503
        failed = [name for name, ok in [("database", db_ok), ("redis", redis_ok)] if not ok]
        return {"status": "not_ready", "failed_dependencies": failed}
    """
    raise NotImplementedError


@router.get("/metrics")
async def metrics():
    """
    Prometheus text format: request count, request latency histogram, triage
    latency, fallback counter (§2.2).

    TODO(you): define your Counter/Histogram objects (probably in a new
    app/observability.py) and increment them from app/middleware.py (HTTP
    metrics) and app/services/triage_orchestrator.py (triage metrics). Then:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    """
    raise NotImplementedError
