# ADR 0004: PII and Data Governance in the Triage Pipeline

## Status
TODO(you): Proposed / Accepted — the assignment explicitly says this is "CLO
8 arriving in its natural habitat" and worth more at interview than the rest
of the repo (§2.5) — don't leave this one thin.

## Context
Citizen complaints (backend/app/schemas/complaint.py's `text`,
`reporter_contact`, and free-text `location`) may contain names, addresses,
and phone numbers. If TRIAGE_PROVIDER=llm and you're on Google AI Studio's
free tier specifically, the spec notes Google may use inputs to improve its
models on that tier — TODO(you): re-verify this against the provider's
current terms before you finalize this ADR; free-tier data policies change.

## Decision
TODO(you): Pick one, explicitly, and justify it:
  1. Redact PII from complaint text before sending to any LLM provider
  2. Send only the complaint body (drop reporter_contact, generalize location)
  3. Accept and document the exposure (e.g. because you're using Groq, whose
     terms differ from Google's free tier — verify this claim yourself)
Also state your provider choice's actual policy, sourced from where you
checked it, not assumed.

## Consequences
TODO(you): What does your choice cost in triage quality (e.g. does
redacting location hurt category/priority accuracy)? What does it cost in
implementation effort (redaction logic, tested how)?

## Alternatives considered
TODO(you): At minimum: Ollama (fully offline, no PII ever leaves the
machine — the spec calls this out as the zero-exposure option) as the
alternative to whatever hosted provider you chose.
