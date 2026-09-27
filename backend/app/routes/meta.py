"""
GET /api/meta/providers — which triage provider is active, and the last 20
triage outcomes (provider, latency ms, fallback y/n). This is the
observability surface called out in §2.2.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/meta", tags=["meta"])

# TODO(you): decide how to store "last 20 triage outcomes" — an in-memory
# ring buffer is simplest and fine for this assignment (note in your notes
# that it resets per-pod / doesn't aggregate across replicas — that's an
# honest, defensible limitation to name at viva), or persist to Redis if you
# want it shared across pods.


@router.get("/providers")
async def get_provider_meta():
    """
    TODO(you): return something like:
        {
            "active_provider": settings.triage_provider,
            "recent_outcomes": [
                {"provider": "llm:groq", "latency_ms": 842, "fallback": False},
                ...
            ],
        }
    """
    raise NotImplementedError
