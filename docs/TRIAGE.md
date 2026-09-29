# Triage — how the AI step works

## Contract

`TriageProvider.triage(text, location) -> TriageResult` (`backend/app/providers/triage/base.py`).
`TriageResult` = `category` (6-value enum), `priority` (3-value enum), `summary` (≤ 140 chars,
one line), `confidence` (0–1). `extra="forbid"`.

## Pipeline (`backend/app/services/triage_service.py`)

1. **Cache** — key `triage:v1:<provider>:<sha256(normalised text ␟ normalised location)>`,
   24 h TTL. Normalisation: case-fold + collapse whitespace. Rules provider is not cached.
2. **Call** — wall-clock cap `TRIAGE_TIMEOUT_S` (10 s) on every attempt.
3. **Retry once**, sleeping `uniform(0.2, 0.8)` s, **only** for timeout, 429, 5xx.
   Never for 400s, bad output, missing key or network errors.
4. **Fallback** — `RuleBasedTriage`, stored as `triaged_by = rules:fallback`, one WARNING log
   line with `complaint_id`, `provider`, `error_class`. Fallback results are not cached.
5. **Record** — outcome pushed to a Redis list capped at 20 (`/api/meta/providers`);
   metrics `civicpulse_triage_latency_seconds`, `civicpulse_triage_fallback_total`.

## Structured output and validation

Gemini is called with `responseMimeType: application/json` and a `responseSchema` whose
`category`/`priority` are enums (`prompt.py`). The answer is then validated **again** with
Pydantic (`parse_triage_json`): prose, code fences, out-of-enum values, over-long or
multi-line summaries, extra keys and wrong root types are all rejected → fallback.
Model output is never `eval`'d and never reaches SQL except as bound enum values.

## Prompt-injection guardrail

Complaint text is data: wrapped in `<complaint>…</complaint>`, delimiter-like tags in the
citizen's text neutralised (`<` → `(`), the system instruction says content in the tags is never
an instruction, output constrained to the enum, and re-validated.
Tests: `backend/tests/test_injection.py`.

## PII

See ADR 0004: body + location only, redacted; `reporter_contact` never sent.

## Provider limits (as shown in AI Studio for our key)

Google does not publish one fixed table: the Gemini API docs say limits "depend on a variety of factors (such as
your usage tier) and can be viewed in Google AI Studio", are applied **per project** (not per key), and are "not
guaranteed". So the only honest source is our own project's page:
<https://aistudio.google.com/rate-limit> (free tier), checked on CHECK_DATE.

| Model | RPM | RPD | TPM | Checked on |
|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 15 | 500 | 250k | 26-09-2026 |

How the limits shaped the design: the per-IP limit of 10 requests/min (`backend/app/config.py:51`) keeps one client
from spending the project's RPM; the 24 h content-hash cache means repeated reports cost no quota; a 429 is retried
once with jitter and then falls back to rules instead of queueing (`backend/app/services/triage_service.py`).

## Measured triage-cache hit rate

Workload: `scripts/measure_triage_cache.py` — 40 submissions, of which 30 unique texts and 10 repeats that differ
only by letter case or whitespace (a burst-main report forwarded in a neighbourhood group, a streetlight and a
garbage report re-submitted). One paraphrase of the burst-main report is counted as unique. Counters reset first;
provider `simulated` so the run is repeatable. Raw output: `docs/evidence/triage-cache-measurement.txt`.

| Submissions | Unique texts | Hits | Misses | Hit rate |
|---|---|---|---|---|
| 40 | 30 | 10 | 30 | **25 %** |

Every exact repeat hit after normalisation; the paraphrase missed. The cache therefore saves quota on
copy-paste duplicates only — semantic duplicates ("water main break" vs "water main burst") still cost a call.
The hit rate is a property of the workload, not of the code: with no duplicates it is 0 %.

## Latency

End-to-end `POST /api/complaints` with the backend run directly (`python -m app`) against local Postgres 16 and Redis 7 — includes the DB insert and Redis round-trips — from the same runs:

| Provider path | p50 ms | p95 ms | Notes |
|---|---|---|---|
| `simulated` (and cache hits) | 8 | 11 | no network; the floor of the request path |
| `rules:fallback` after a 503 | 468 | 734 | one failed attempt + one retry after a 0.2–0.8 s jittered sleep, then rules |
| `llm:gemini` | GEMINI_P50 | GEMINI_P95 | from `/api/meta/providers` → `recent[].latency_ms` with our key |
| `llm:ollama` (CPU) | not run | not run | optional `--profile ollama`; not measured |

The fallback row is the cost of resilience: a failing provider adds roughly half a second per complaint, bounded
by one retry — never the 10 s timeout twice unless the provider actually hangs.
