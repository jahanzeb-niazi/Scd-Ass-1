# ADR 0001 — Triage behind a provider interface

**Status:** Accepted · **Date:** 2026-09-27

## Context

Complaint triage (category, priority, one-line summary) is done by a component we do not
control and expect to replace: keyword rules today, a hosted LLM now, perhaps a fine-tuned
classifier later. That component can be rate-limited, slow, wrong, or down. The rest of the
system must not care which implementation is active, and must never fail because of it.

## Decision

1. **One interface.** `TriageProvider` (a `typing.Protocol`) in
   `backend/app/providers/triage/base.py`: `name: str` and
   `triage(text, location) -> TriageResult`. `TriageResult` is a Pydantic model with
   `extra="forbid"` — the same validation machinery we use for HTTP input.
2. **Four implementations**, selected by `TRIAGE_PROVIDER` in `factory.py`:
   | value | class | `triaged_by` | use |
   |---|---|---|---|
   | `llm` | `LLMTriage` (Gemini) | `llm:gemini` | production |
   | `ollama` | `OllamaTriage` | `llm:ollama` | offline / no PII egress |
   | `rules` | `RuleBasedTriage` | `rules` | deterministic, always available |
   | `simulated` | `SimulatedTriage` | `simulated` | CI: seeded, no network, failure injection |
3. **Providers only classify their own failures** (`retryable` or not). The *policy* lives
   in one place, `services/triage_service.py`:
   content-hash cache (24 h) → wall-clock cap 10 s → one jittered retry on timeout/429/5xx
   only → fallback to `RuleBasedTriage`, recorded as `rules:fallback`. Fallbacks are not cached.
4. **The provider name doubles as the stored `triaged_by` value**, so provenance is recorded
   without a mapping table.
5. **Hosted provider: Google Gemini (AI Studio free tier)**, chosen by the team over Groq.
   Consequence: the free tier may use inputs to improve Google's models, which is handled in
   ADR 0004.

## Consequences

- Swapping the model is a new class plus one line in the factory; routes, services, schema
  and tests are unchanged.
- CI is deterministic by construction (`TRIAGE_PROVIDER=simulated`), and failure paths are
  tested with injected fakes (`tests/fakes.py`), never with `sleep()` or re-runs.
- A missing `GEMINI_API_KEY` is not fatal: every triage falls back to rules and the
  fallback is visible in `/api/meta/providers`. A clean clone always runs.
- `llm:groq` exists in the `triage_source` enum so a Groq provider can be added later
  without a migration.
