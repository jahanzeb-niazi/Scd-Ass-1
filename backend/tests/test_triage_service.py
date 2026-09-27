"""TriageService policy: timeout, single retry on retryable errors, cache, fallback."""

from __future__ import annotations

import uuid

import fakeredis

from app.domain import TriagedBy
from app.providers.cache import RedisCache
from app.providers.triage.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
)
from app.providers.triage.simulated import SimulatedTriage
from app.services.triage_service import TriageService, content_hash
from tests.fakes import AlwaysRaises, Blocks, Scripted

CID = uuid.UUID(int=1)


def _service(provider: object, **kw: object) -> tuple[TriageService, list[float]]:
    slept: list[float] = []
    cache = RedisCache(fakeredis.FakeRedis(decode_responses=True))
    svc = TriageService(provider, cache, jitter_s=(0.2, 0.8), sleep=slept.append, **kw)  # type: ignore[arg-type]
    return svc, slept


def test_retries_once_with_jitter_on_retryable_then_succeeds() -> None:
    provider = Scripted(ProviderRateLimitedError("429"))
    svc, slept = _service(provider)
    out = svc.triage(CID, "pothole on road", "x")
    assert provider.calls == 2
    assert out.fallback is False and out.triaged_by is TriagedBy.LLM_GEMINI
    assert len(slept) == 1 and 0.2 <= slept[0] <= 0.8


def test_retries_only_once() -> None:
    provider = Scripted(ProviderServerError("503"), ProviderServerError("503"))
    svc, slept = _service(provider)
    out = svc.triage(CID, "pothole on road", "x")
    assert provider.calls == 2 and len(slept) == 1
    assert out.fallback is True and out.error == "ProviderServerError"


def test_never_retries_400_or_bad_output() -> None:
    for err in (ProviderRequestError("400"), ProviderOutputError("prose")):
        provider = Scripted(err)
        svc, slept = _service(provider)
        out = svc.triage(CID, "pothole on road", "x")
        assert provider.calls == 1 and slept == []
        assert out.triaged_by is TriagedBy.RULES_FALLBACK


def test_hard_timeout_caps_a_hanging_provider() -> None:
    provider = Blocks()
    svc, _ = _service(provider, timeout_s=0.05)
    try:
        out = svc.triage(CID, "water main burst", "x")
    finally:
        provider.release.set()
        svc.close()
    assert out.fallback is True
    assert out.error == "ProviderTimeoutError"
    assert provider.calls == 2  # timeout is retryable: one retry, then fallback


def test_duplicate_complaints_cost_one_inference() -> None:
    provider = Scripted()
    svc, _ = _service(provider)
    first = svc.triage(CID, "Burst main on  Street 12", "Gulshan")
    second = svc.triage(CID, "burst main on street 12", "  GULSHAN ")  # normalised → same hash
    assert provider.calls == 1
    assert (first.cache_hit, second.cache_hit) == (False, True)
    assert second.result == first.result
    assert svc.cache_counters() == (1, 1)


def test_fallback_results_are_not_cached() -> None:
    provider = AlwaysRaises(ProviderRequestError)
    svc, _ = _service(provider)
    svc.triage(CID, "water leak", "x")
    svc.triage(CID, "water leak", "x")
    assert provider.calls == 2  # second call tried the provider again


def test_content_hash_ignores_case_and_whitespace_only() -> None:
    assert content_hash("A  b", "C") == content_hash("a b", " c ")
    assert content_hash("a b", "c") != content_hash("a b", "d")


def test_recent_outcomes_are_capped_at_20() -> None:
    svc, _ = _service(SimulatedTriage())
    for i in range(25):
        out = svc.triage(CID, f"water leak number {i}", "x")
        svc.record(uuid.UUID(int=i), out)
    recent = svc.recent()
    assert len(recent) == 20
    assert recent[0].complaint_id == str(uuid.UUID(int=24))  # newest first
