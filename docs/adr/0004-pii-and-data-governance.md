# ADR 0004 — PII and data governance for hosted triage

**Status:** Accepted · **Date:** 2026-09-27

## Context

We triage with Google Gemini on the AI Studio free tier (ADR 0001). On that tier Google may
use submitted inputs to improve its models. Citizen complaints routinely contain names,
street addresses, phone numbers, email addresses and CNIC numbers. Whatever we send is data
leaving our infrastructure to a third party, under terms we do not control.

## Decision

**Send the minimum, and scrub what we send.**

| Field | Sent to Gemini? | Why |
|---|---|---|
| `reporter_contact` | **Never** | Not needed to classify a complaint. It stays in PostgreSQL. |
| `text` (complaint body) | Yes, **after redaction** | This is the signal the model classifies. |
| `location` | Yes, **after redaction** | Helps disambiguate (a *nala* vs a road); street-level only. |
| complaint `id`, timestamps, status | Never | No classification value. |

Redaction (`backend/app/providers/triage/pii.py`) replaces e-mail addresses → `[EMAIL]`,
Pakistani CNICs → `[CNIC]`, and phone numbers / long digit runs → `[PHONE]` before the
request is built. It is applied only in `LLMTriage`: the Ollama path never leaves the machine.

Further controls:

- The API key travels in the `x-goog-api-key` header, never the URL, so it cannot appear in
  logs, exception messages or proxy access logs. It comes from the environment only.
- Logs never contain complaint text. The fallback WARNING carries only the complaint id,
  provider and error class.
- The triage cache key is a SHA-256 of the normalised text + location; raw text is not
  used as a Redis key.
- The frontend tells citizens their contact is never sent to the AI service.

## Accepted residual risk

Regex redaction is best-effort. Names ("Mr. Aslam in House 45") and free-form addresses in
the body are **not** removed. We accept that exposure for this coursework system because the
body is needed for classification, and we document it rather than claim otherwise.

**Exit route:** set `TRIAGE_PROVIDER=ollama` and no complaint data leaves the machine at all,
at the cost of slower, weaker classification (the buy-vs-host trade-off). A production
deployment handling real citizen data would move to a paid tier with a no-training data
agreement, or to self-hosting.
