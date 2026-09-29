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

## Provider limits (fill in what YOU saw)

> The assignment requires citing the limits you actually observed on the provider's
> live page. Open AI Studio → *Usage / Rate limits* for your key and record them here.

| Model | RPM | RPD | TPM | Checked on |
|---|---|---|---|---|
| `gemini-2.5-flash-lite` | _fill in_ | _fill in_ | _fill in_ | _date_ |

## Measured triage-cache hit rate (fill in from your run)

Procedure:

```bash
docker compose exec cache redis-cli DEL triage:cache:hits triage:cache:misses
# submit your demo complaints, including a few duplicates (e.g. 9 neighbours × 1 burst main)
curl -s localhost:8000/api/meta/providers | jq .cache
```

| Submissions | Unique texts | Hits | Misses | Hit rate |
|---|---|---|---|---|
| _fill in_ | _fill in_ | _fill in_ | _fill in_ | _fill in_ |

## Latency (fill in)

From `/api/meta/providers` or Grafana panel "Triage latency p95 by provider":

| Provider | p50 ms | p95 ms | Notes |
|---|---|---|---|
| llm:gemini | | | |
| llm:ollama (CPU) | | | buy-vs-host: slower, weaker classification |
| rules | ~0–10 | | deterministic |
