"""
/health must never touch the database (§2.2) — this test is partly about
correctness, partly a guard rail so nobody "fixes" /health later by adding a
DB check and silently breaks the liveness/readiness distinction.
"""
import pytest


@pytest.mark.anyio
async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


# TODO(you): test_ready_returns_503_when_db_unreachable — mock db_is_reachable
# to return False and assert response.status_code == 503 and the body names
# "database" as the failed dependency.

# TODO(you): test_ready_returns_200_when_all_healthy
