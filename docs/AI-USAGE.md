# AI Usage Disclosure

Per §5.5: "the rule is honest attribution, not avoidance... Specific
disclosure carries no penalty whatsoever." Presenting AI-generated work as
your own original work without disclosure is plagiarism under course policy —
fill this in honestly and specifically, not with a vague blanket statement.

## Tools used
TODO(you): name the actual tool(s) — e.g. "Claude (claude.ai)", "GitHub
Copilot", etc. — and roughly when/how (chat-based scaffolding vs. inline
autocomplete).

## What AI wrote or shaped

TODO(you): be specific per layer/file, e.g.:
- Backend scaffolding (routes/services/repositories/providers skeleton,
  Dockerfiles, K8s manifests, CI/CD workflows): AI-generated structure,
  following the assignment spec, with business logic left as TODOs
- `app/services/triage_orchestrator.py`, `app/services/state_machine.py`,
  actual triage logic, actual test implementations: TODO(you) — fill in as
  YOU write these
- Frontend components: TODO(you)

## What you changed afterward, and why

TODO(you): this is the part that actually matters at viva — for anything AI
scaffolded, note what you had to fix, rewrite, or reject, and why. A viva
question like "why is the fallback logic structured this way" needs an answer
that's true regardless of who typed the first draft.

## What you wrote yourself, unassisted

TODO(you): name it explicitly. The rubric and this file both exist because
the assignment wants you to be able to point at specific decisions (the
TriageProvider interface design, the four-layer boundaries, the PII ADR, the
8 engineering-notes answers with real measured numbers) as genuinely yours.
