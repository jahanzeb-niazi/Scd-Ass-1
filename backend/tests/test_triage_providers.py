"""Unit tests for the triage pieces that need no database."""

from __future__ import annotations

import json

import httpx
import pytest

from app.domain import Category, Priority
from app.providers.triage.base import (
    ProviderOutputError,
    ProviderRateLimitedError,
    ProviderRequestError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TriageProvider,
    parse_triage_json,
)
from app.providers.triage.factory import build_provider
from app.providers.triage.llm import LLMTriage
from app.providers.triage.ollama import OllamaTriage
from app.providers.triage.pii import redact
from app.providers.triage.rules import RuleBasedTriage
from app.providers.triage.simulated import SimulatedTriage
from tests.conftest import make_settings

GOOD = {"category": "water", "priority": "high", "summary": "Burst main", "confidence": 0.9}


# ------------------------------------------------------------- validation
def test_valid_json_is_accepted() -> None:
    r = parse_triage_json(json.dumps(GOOD))
    assert (r.category, r.priority) == (Category.WATER, Priority.HIGH)


@pytest.mark.parametrize(
    "raw",
    [
        "This is a water complaint.",  # prose
        "```json\n" + json.dumps(GOOD) + "\n```",  # code fence
        json.dumps({**GOOD, "category": "flooding"}),  # plausible but not in enum
        json.dumps({**GOOD, "priority": "urgent"}),
        json.dumps({**GOOD, "summary": "x" * 400}),  # 400-char "one-line" summary
        json.dumps({**GOOD, "summary": "line one\nline two"}),
        json.dumps({**GOOD, "confidence": 1.5}),
        json.dumps({**GOOD, "override": True}),  # extra keys
        json.dumps([GOOD]),  # wrong root type
        "",
    ],
)
def test_malformed_output_is_rejected(raw: str) -> None:
    with pytest.raises(ProviderOutputError):
        parse_triage_json(raw)


# ------------------------------------------------------------------ rules
@pytest.mark.parametrize(
    ("text", "category", "priority"),
    [
        ("Burst water main flooding Street 12, water entering ground floors", "water", "high"),
        ("Bijli ka taar gir gaya, sparking near school", "electricity", "high"),
        ("Gutter overflow for one week, kachra everywhere", "sanitation", "normal"),
        ("Big pothole on the main sarak near chowrangi", "roads", "normal"),
        ("Streetlights off for 3 weeks, andhera hai", "streetlights", "normal"),
        ("Suggestion: please paint zebra crossing", "roads", "low"),
        ("Stray dogs barking all night in our lane", "other", "normal"),
    ],
)
def test_rules_classify_urdu_influenced_english(text: str, category: str, priority: str) -> None:
    r = RuleBasedTriage().triage(text, "Karachi")
    assert (r.category.value, r.priority.value) == (category, priority)
    assert len(r.summary) <= 140


@pytest.mark.parametrize("text", ["", " ", "🙂" * 3000, "\x00\n\t", "a" * 5000])
def test_rules_never_raise(text: str) -> None:
    r = RuleBasedTriage().triage(text, "")
    assert len(r.summary) <= 140


# -------------------------------------------------------------------- pii
def test_redaction_removes_direct_identifiers() -> None:
    raw = (
        "Call me 0300-1234567 or +92 321 7654321, email ali.khan@example.com, CNIC 42101-1234567-1"
    )
    out = redact(raw)
    assert "1234567" not in out and "7654321" not in out
    assert "example.com" not in out and "42101" not in out
    assert out.count("[PHONE]") == 2 and "[EMAIL]" in out and "[CNIC]" in out


# -------------------------------------------------------------- simulated
def test_simulated_is_deterministic() -> None:
    a = SimulatedTriage(seed=7).triage("Pani nahi aa raha", "Orangi")
    b = SimulatedTriage(seed=7).triage("Pani nahi aa raha", "Orangi")
    assert a == b


@pytest.mark.parametrize(
    ("mode", "exc"),
    [
        ("error", ProviderServerError),
        ("timeout", ProviderTimeoutError),
        ("rate_limit", ProviderRateLimitedError),
        ("bad_request", ProviderRequestError),
        ("malformed", ProviderOutputError),
    ],
)
def test_simulated_failure_injection(mode: str, exc: type[Exception]) -> None:
    with pytest.raises(exc):
        SimulatedTriage(failure_mode=mode, failure_rate=1.0).triage("water leak here", "x")


# ------------------------------------------------------------------- llm
def _gemini(status: int, body: object) -> tuple[LLMTriage, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMTriage("secret-key", "gemini-test", "https://gemini.test/v1beta", client=client), seen


def _candidate(text: str) -> dict[str, object]:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_success_and_key_only_in_header() -> None:
    llm, seen = _gemini(200, _candidate(json.dumps(GOOD)))
    r = llm.triage("Burst main. Call 0300-1234567", "Street 12")
    assert r.category is Category.WATER
    req = seen[0]
    assert "secret-key" not in str(req.url)
    assert req.headers["x-goog-api-key"] == "secret-key"
    body = json.loads(req.content)
    assert "0300-1234567" not in json.dumps(body)  # redacted before leaving
    assert body["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (429, ProviderRateLimitedError),
        (500, ProviderServerError),
        (503, ProviderServerError),
        (400, ProviderRequestError),
        (403, ProviderRequestError),
    ],
)
def test_gemini_http_errors_are_classified(status: int, exc: type[Exception]) -> None:
    llm, _ = _gemini(status, {"error": {"message": "x"}})
    with pytest.raises(exc):
        llm.triage("water leak", "x")


def test_gemini_missing_candidate_is_output_error() -> None:
    llm, _ = _gemini(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    with pytest.raises(ProviderOutputError):
        llm.triage("water leak", "x")


def test_gemini_without_key_is_unavailable() -> None:
    with pytest.raises(ProviderUnavailableError):
        LLMTriage("", "m", "https://x").triage("water leak", "x")


def test_gemini_timeout_is_retryable_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    llm = LLMTriage(
        "k", "m", "https://x", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderTimeoutError):
        llm.triage("water leak", "x")


def test_ollama_parses_structured_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)}})

    ollama = OllamaTriage(
        "http://ollama:11434",
        "llama3.2:1b",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert ollama.triage("water leak", "x").category is Category.WATER


# --------------------------------------------------------------- factory
@pytest.mark.parametrize(
    ("choice", "name"),
    [
        ("llm", "llm:gemini"),
        ("ollama", "llm:ollama"),
        ("rules", "rules"),
        ("simulated", "simulated"),
    ],
)
def test_factory_selects_by_env(choice: str, name: str) -> None:
    provider = build_provider(make_settings(triage_provider=choice))
    assert isinstance(provider, TriageProvider)
    assert provider.name == name


def test_gemini_error_message_is_surfaced_without_the_key() -> None:
    body = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}}
    llm, _ = _gemini(400, body)
    with pytest.raises(ProviderRequestError) as info:
        llm.triage("water leak", "x")
    assert "API key not valid" in str(info.value)
    assert "secret-key" not in str(info.value)
