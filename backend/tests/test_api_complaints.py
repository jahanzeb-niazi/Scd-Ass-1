"""HTTP contract tests against a real PostgreSQL."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from tests.conftest import VALID, ClientFactory


def test_create_then_get(client: TestClient) -> None:
    resp = client.post("/api/complaints", json={**VALID, "reporter_contact": "0300-1112223"})
    assert resp.status_code == 201
    body = resp.json()
    assert resp.headers["location"] == f"/api/complaints/{body['id']}"
    assert body["status"] == "open"
    assert body["triaged_by"] == "simulated"
    assert body["category"] == "water" and body["priority"] == "high"
    assert 0 < len(body["ai_summary"]) <= 140
    assert body["allowed_transitions"] == ["in_progress", "rejected"]
    assert body["created_at"].endswith("Z")  # UTC

    got = client.get(f"/api/complaints/{body['id']}")
    assert got.status_code == 200
    assert got.json()["reporter_contact"] == "0300-1112223"


def test_validation_errors_are_field_level_400(client: TestClient) -> None:
    resp = client.post(
        "/api/complaints", json={"text": "short", "location": "ab", "reporter_contact": "x" * 201}
    )
    assert resp.status_code == 400
    fields = {e["field"] for e in resp.json()["errors"]}
    assert fields == {"text", "location", "reporter_contact"}


def test_unknown_fields_and_bad_json_are_400(client: TestClient) -> None:
    assert client.post("/api/complaints", json={**VALID, "priority": "high"}).status_code == 400
    bad = client.post(
        "/api/complaints", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert bad.status_code == 400


def test_whitespace_is_trimmed_before_length_checks(client: TestClient) -> None:
    resp = client.post("/api/complaints", json={"text": "   short    ", "location": "Block 4"})
    assert resp.status_code == 400


def test_get_unknown_is_404_and_bad_uuid_is_400(client: TestClient) -> None:
    assert client.get(f"/api/complaints/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/complaints/not-a-uuid").status_code == 400


def test_list_filters_paginates_and_returns_total(client: TestClient) -> None:
    texts = [
        ("Burst water main flooding the street", "water"),
        ("Pani nahi aa raha for four days", "water"),
        ("Transformer blasted, no bijli all night", "electricity"),
    ]
    for text, _ in texts:
        assert (
            client.post("/api/complaints", json={"text": text, "location": "Karachi"}).status_code
            == 201
        )

    page1 = client.get("/api/complaints", params={"category": "water", "page_size": 1}).json()
    assert page1["total"] == 2 and len(page1["items"]) == 1 and page1["page"] == 1
    page2 = client.get(
        "/api/complaints", params={"category": "water", "page_size": 1, "page": 2}
    ).json()
    assert page2["items"][0]["id"] != page1["items"][0]["id"]
    # newest first
    all_items = client.get("/api/complaints").json()["items"]
    assert [i["created_at"] for i in all_items] == sorted(
        (i["created_at"] for i in all_items), reverse=True
    )
    assert client.get("/api/complaints", params={"status": "resolved"}).json()["total"] == 0


def test_list_rejects_bad_query_params(client: TestClient) -> None:
    assert client.get("/api/complaints", params={"page_size": 101}).status_code == 400
    assert client.get("/api/complaints", params={"page": 0}).status_code == 400
    r = client.get("/api/complaints", params={"category": "potholes"})
    assert r.status_code == 400 and r.json()["errors"][0]["field"] == "category"


def test_status_transitions_follow_the_state_machine(client: TestClient) -> None:
    cid = client.post("/api/complaints", json=VALID).json()["id"]
    url = f"/api/complaints/{cid}/status"

    r = client.patch(url, json={"status": "resolved"})
    assert r.status_code == 409
    body = r.json()
    assert "open → resolved" in body["detail"]
    assert (body["current"], body["attempted"]) == ("open", "resolved")
    assert body["allowed"] == ["in_progress", "rejected"]

    r = client.patch(url, json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["allowed_transitions"] == ["resolved", "rejected"]
    assert r.json()["updated_at"] >= r.json()["created_at"]

    assert client.patch(url, json={"status": "resolved"}).status_code == 200
    terminal = client.patch(url, json={"status": "rejected"})
    assert terminal.status_code == 409
    assert "terminal" in terminal.json()["detail"]


def test_status_patch_validation_and_404(client: TestClient) -> None:
    assert (
        client.patch(
            f"/api/complaints/{uuid.uuid4()}/status", json={"status": "resolved"}
        ).status_code
        == 404
    )
    cid = client.post("/api/complaints", json=VALID).json()["id"]
    assert client.patch(f"/api/complaints/{cid}/status", json={"status": "done"}).status_code == 400


def test_stats_cache_miss_hit_and_invalidation_on_write(client: TestClient) -> None:
    first = client.get("/api/stats")
    assert first.headers["x-cache"] == "MISS"
    assert first.json()["total"] == 0
    assert client.get("/api/stats").headers["x-cache"] == "HIT"

    cid = client.post("/api/complaints", json=VALID).json()["id"]
    after_write = client.get("/api/stats")
    assert after_write.headers["x-cache"] == "MISS"  # invalidated, not left to expire
    assert after_write.json()["total"] == 1
    assert after_write.json()["by_category"]["water"] == 1
    assert after_write.json()["by_status"]["open"] == 1

    client.get("/api/stats")
    client.patch(f"/api/complaints/{cid}/status", json={"status": "in_progress"})
    after_patch = client.get("/api/stats")
    assert after_patch.headers["x-cache"] == "MISS"
    assert after_patch.json()["by_status"]["in_progress"] == 1


def test_rate_limit_returns_429_with_retry_after(make_client: ClientFactory) -> None:
    client = make_client(rate_limit_requests=2)
    hdr = {"X-Forwarded-For": "203.0.113.7"}
    assert client.post("/api/complaints", json=VALID, headers=hdr).status_code == 201
    ok = client.post("/api/complaints", json=VALID, headers=hdr)
    assert ok.headers["x-ratelimit-remaining"] == "0"
    limited = client.post("/api/complaints", json=VALID, headers=hdr)
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["retry-after"]) <= 60
    assert "Try again" in limited.json()["detail"]
    # A different client is unaffected.
    other = client.post("/api/complaints", json=VALID, headers={"X-Forwarded-For": "198.51.100.1"})
    assert other.status_code == 201


def test_rate_limit_uses_rightmost_forwarded_for(make_client: ClientFactory) -> None:
    client = make_client(rate_limit_requests=1)
    # A client cannot dodge the limit by prepending a fake address.
    assert (
        client.post(
            "/api/complaints", json=VALID, headers={"X-Forwarded-For": "1.1.1.1, 203.0.113.9"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/complaints", json=VALID, headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.9"}
        ).status_code
        == 429
    )


def test_meta_providers_reports_triage_cache_hit_rate(client: TestClient) -> None:
    client.post("/api/complaints", json=VALID)
    second = client.post("/api/complaints", json=VALID).json()
    assert second["triage"]["cache_hit"] is True

    meta = client.get("/api/meta/providers").json()
    assert meta["active"] == "simulated" and meta["configured"] == "simulated"
    assert meta["fallback"] == "rules:fallback"
    assert meta["cache"] == {"hits": 1, "misses": 1, "hit_rate": 0.5}
    assert len(meta["recent"]) == 2 and meta["recent"][0]["cache_hit"] is True
    assert {"provider", "latency_ms", "fallback"} <= set(meta["recent"][0])
