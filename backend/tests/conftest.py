"""
Shared pytest fixtures. Tests MUST run against TRIAGE_PROVIDER=simulated so
the suite is deterministic on every run (§2.5 "Determinism, and how to test a
system that is not").
"""
from __future__ import annotations

import os

os.environ.setdefault("TRIAGE_PROVIDER", "simulated")
os.environ.setdefault("ENVIRONMENT", "ci")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """
    TODO(you): once DB/session wiring is real, this fixture should also:
      - point at a test database (or use a transactional rollback-per-test pattern)
      - override the get_complaint_service dependency as needed per-test
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# TODO(you): add a fixture that builds a ComplaintService wired to
# SimulatedTriage(fail_mode="raise") specifically for the fallback test —
# see tests/test_triage_fallback.py.
