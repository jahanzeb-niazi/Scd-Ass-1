# ADR 0001: Triage Provider Interface

## Status
TODO(you): Proposed / Accepted — set once your team has actually decided.

## Context
TODO(you): Explain the problem in your own words — the assignment's framing
(§1.1–1.3) is that the AI triage component is unreliable-by-nature and must
be replaceable without the rest of the system caring which implementation is
behind it. Summarize why that matters for CivicPulse specifically.

## Decision
TODO(you): Describe the `TriageProvider` Protocol (backend/app/providers/triage/base.py)
and why a Python `Protocol` (structural typing) was chosen over, say, an ABC
with inheritance, or duck typing with no interface at all. Reference the four
concrete implementations (simulated, rules, llm, ollama) and how
TRIAGE_PROVIDER selects between them (factory.py).

## Consequences
TODO(you): What does this buy you? (e.g. CI can pin to SimulatedTriage for
determinism, RuleBasedTriage guarantees the system never hard-fails, adding a
5th provider later — a fine-tuned classifier, per §1.1's own example — needs
no changes outside providers/triage/.) What does it cost? (e.g. every
provider must independently handle its own timeout/error signaling in a way
the orchestrator can interpret uniformly.)

## Alternatives considered
TODO(you): At minimum, address: (a) calling the LLM directly from the service
layer with no interface, (b) a single class with an if/elif branch on provider
type instead of separate classes. Explain why you rejected each.
