"""Operational endpoints, logging, and the seed."""

from __future__ import annotations

import json
import logging

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import seed
from app.config import get_settings
from app.container import Container
from app.logging_config import JsonFormatter, request_id_var
from app.main import create_app
from tests.conftest import VALID, make_settings


def test_health_does_not_touch_the_database() -> None:
    # Point at a database that does not exist: liveness must still be 200,
    # readiness must be 503 and name the failed dependency.
    settings = make_settings(
        database_url="postgresql://x:y@127.0.0.1:1/nope", db_connect_timeout_s=1
    )
    container = Container.build(settings, redis_client=fakeredis.FakeRedis(decode_responses=True))
    with TestClient(create_app(settings, container=container)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        ready = client.get("/ready")
        assert ready.status_code == 503
        assert ready.json()["failed"] == ["postgres"]
    container.close()


def test_ready_is_200_when_dependencies_are_up(client: TestClient) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == {"postgres": "ok", "redis": "ok"}


def test_ready_is_503_while_draining(client: TestClient) -> None:
    client.app.state.container.lifecycle.draining = True  # type: ignore[attr-defined]
    r = client.get("/ready")
    assert r.status_code == 503 and "shutdown" in r.json()["failed"]


def test_request_id_is_propagated_or_generated(client: TestClient) -> None:
    assert (
        client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"]
        == "abc-123"
    )
    generated = client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert generated.headers["x-request-id"] != "bad id with spaces"
    assert len(generated.headers["x-request-id"]) == 32


def test_metrics_exposes_prometheus_text(client: TestClient) -> None:
    client.post("/api/complaints", json=VALID)
    body = client.get("/metrics").text
    for metric in (
        "civicpulse_http_requests_total",
        "civicpulse_http_request_duration_seconds_bucket",
        "civicpulse_triage_latency_seconds_bucket",
        "civicpulse_triage_fallback_total",
    ):
        assert metric in body
    assert 'route="/api/complaints"' in body  # route template, not raw path


def test_json_log_lines_carry_request_id() -> None:
    token = request_id_var.set("rid-42")
    try:
        record = logging.LogRecord("t", logging.WARNING, __file__, 1, "triage fallback", None, None)
        record.complaint_id = "c1"
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "rid-42"
    assert line["level"] == "WARNING" and line["complaint_id"] == "c1"


def test_seed_is_idempotent(clean_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", clean_db)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    try:
        first = seed.run()
        second = seed.run()
    finally:
        get_settings.cache_clear()
    assert first == len(seed.SEED) >= 30
    assert second == 0

    engine = create_engine(make_settings().sqlalchemy_url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM complaints")).scalar_one()
        cats = conn.execute(text("SELECT count(DISTINCT category) FROM complaints")).scalar_one()
    engine.dispose()
    assert count == len(seed.SEED)
    assert cats == 6  # spread across every category


def test_database_enforces_length_rules_too(clean_db: str) -> None:
    engine = create_engine(make_settings().sqlalchemy_url)
    with pytest.raises(Exception, match="ck_complaints_text_len"), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO complaints (text, location, category, priority, triaged_by,"
                " triage_latency_ms) VALUES ('short', 'Block 4', 'water', 'high', 'rules', 0)"
            )
        )
    engine.dispose()


def test_redis_outage_degrades_instead_of_failing(clean_db: str) -> None:
    # Redis unreachable: submissions still succeed (rate limiter fails open,
    # triage cache is skipped), stats are served from the DB as MISS, and
    # /ready reports redis so the pod leaves the Service.
    from app.providers.cache import build_redis_client

    settings = make_settings()
    dead = build_redis_client("redis://127.0.0.1:1/0", timeout_s=0.2)
    container = Container.build(settings, redis_client=dead)
    with TestClient(create_app(settings, container=container)) as client:
        assert client.post("/api/complaints", json=VALID).status_code == 201
        stats = client.get("/api/stats")
        assert stats.status_code == 200 and stats.headers["x-cache"] == "MISS"
        assert client.get("/api/meta/providers").json()["recent"] == []
        ready = client.get("/ready")
        assert ready.status_code == 503 and ready.json()["failed"] == ["redis"]
    container.close()
