"""THE test (spec §2.5): given a provider that always raises,
POST /api/complaints still returns 201 and triaged_by == "rules:fallback"."""

from __future__ import annotations

import pytest

from app.providers.triage.base import (
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from tests.conftest import VALID, ClientFactory
from tests.fakes import AlwaysRaises, ReturnsRaw


@pytest.mark.parametrize(
    ("exc", "expected_calls"),
    [
        (ProviderServerError, 2),  # 5xx: retried once
        (ProviderRateLimitedError, 2),  # 429: retried once
        (ProviderTimeoutError, 2),  # timeout: retried once
        (ProviderRequestError, 1),  # 400: never retried
        (ProviderUnavailableError, 1),  # no key / network: not in the retry list
        (RuntimeError, 1),  # a provider bug still never becomes a 500
    ],
)
def test_provider_that_always_raises_still_returns_201_with_rules_fallback(
    make_client: ClientFactory, exc: type[Exception], expected_calls: int
) -> None:
    provider = AlwaysRaises(exc)
    client = make_client(provider=provider)

    resp = client.post("/api/complaints", json=VALID)

    assert resp.status_code == 201
    body = resp.json()
    assert body["triaged_by"] == "rules:fallback"
    assert body["triage"]["fallback"] is True
    assert body["category"] == "water"  # decided by RuleBasedTriage
    assert provider.calls == expected_calls

    # ...and it was persisted that way.
    stored = client.get(f"/api/complaints/{body['id']}").json()
    assert stored["triaged_by"] == "rules:fallback"


def test_malformed_model_output_is_rejected_and_falls_back(make_client: ClientFactory) -> None:
    provider = ReturnsRaw("Sure! Category: water, priority: high.")
    client = make_client(provider=provider)

    resp = client.post("/api/complaints", json=VALID)

    assert resp.status_code == 201
    assert resp.json()["triaged_by"] == "rules:fallback"
    assert provider.calls == 1  # bad output is not retryable


def test_fallback_is_recorded_in_meta_providers(make_client: ClientFactory) -> None:
    client = make_client(provider=AlwaysRaises())
    cid = client.post("/api/complaints", json=VALID).json()["id"]

    meta = client.get("/api/meta/providers").json()

    assert meta["recent"][0]["complaint_id"] == cid
    assert meta["recent"][0]["fallback"] is True
    assert meta["recent"][0]["error"] == "ProviderServerError"
