# AI usage

Per §5.5: honest attribution, specific disclosure.

**Tool:** Claude (Anthropic), used through Claude's agentic workspace — models Claude Opus 5.5 and Claude Sonnet 5.5.
It generated most of the code and documents in this repository from the assignment PDF, asking us for every
decision the PDF did not fix. We then ran, tested and debugged it on our own Windows machines, and brought it into
the repository piece by piece through reviewed pull requests, reading every file before committing it.

| Area | What Claude wrote or shaped | What we changed or found afterwards, and why |
|---|---|---|
| **Backend** (`backend/`) | Four-layer FastAPI app, triage providers and policy, Redis cache and limiter, Alembic migration, seed, 105 tests. | When Gemini triage kept falling back with only `ProviderUnavailableError` in `/api/meta/providers`, we could not tell a bad key from a blocked network. We had the provider errors carry a short, key-free reason (`backend/app/providers/triage/llm.py`, `error_detail`), added it to the fallback WARNING log, and added `python -m app.diagnose` to check key shape, DNS and one real call. The first key in our `.env` was 53 characters long instead of the ~39 of an AI Studio key, which pointed at a copy-paste mistake. |
| **Frontend** (`frontend/`) | Three views, typed client, validation, error boundary, styles, nginx template, 14 Vitest tests. | Ran lint, type-check, tests and build locally; reviewed the 409 and X-Cache behaviour against the running backend. |
| **Containers & Compose** | Both Dockerfiles, `.dockerignore`s, `compose.yaml`, `compose.prod.yaml`, observability profile. | First real builds happened on our machines (Claude's environment could not pull base images). Docker Hub timed out from our network (`TLS handshake timeout`); we configured a registry mirror in Docker Desktop. The build-context sizes in ENGINEERING-NOTES were measured by Claude with `scripts/context-size.sh`; the image sizes are from our own `docker image ls`. |
| **Kubernetes** (`k8s/`, `scripts/*.ps1`, `load/`) | Kustomize base and overlays, HPA/VPA/PDB, bring-up and measurement scripts in bash and PowerShell. | Running `k8s-up.ps1` on Windows exposed three bugs, each fixed and explained in ENGINEERING-NOTES Q8: native stderr under `ErrorActionPreference=Stop`, `-p` captured as `-PipelineVariable`, and the `host.docker.internal` kubeconfig address. Image pulls from inside the k3d nodes still timed out, so we did not complete the local HPA/VPA measurements; we report that instead of estimating numbers (Q5, Q6). |
| **CI/CD** (`.github/workflows/`, `scripts/check_submission.py`) | `ci.yml`, `cd.yml`, `release.yml`, submission self-check. | We noticed CI only ran on PRs into `main`, while the rubric asks for CI "on every PR"; changed `ci.yml` to run on PRs into `dev` as well. Configured repository secrets, branch protection and required checks ourselves. |
| **Docs** | README, ADRs 0001–0004, RUNBOOK, TRIAGE, ENGINEERING-NOTES, this file. | The cache hit rate and fallback latency were measured by Claude running this code against local Postgres and Redis with `scripts/measure_triage_cache.py` (raw output in `docs/evidence/`); anyone can re-run it. Q8 is our own debugging story, written up from the error output we pasted while debugging; provider limits and Gemini latency are copied from our own AI Studio page and `/api/meta/providers`. |

**Decisions that were ours** (Claude asked; we chose): Gemini as the hosted provider; nginx `/api` proxy for
runtime config; send body + location only, redacted, never the contact; fixed-window rate limit 10/min/IP; k3d;
backend egress via the `edge` network; Ollama as an opt-in Compose profile; migrations as a one-shot job; seed on
the dev overlay only; keep the Redis volume (quota state); bonus scope limited to zero-downtime rollout,
digest + Cosign, Prometheus + Grafana; stop local Kubernetes work after the image-pull problem and prioritise the
AI layer, backend and CI/CD (the order of value given in §5.1).

**What we verified ourselves:** backend lint, types and the full test suite; frontend lint, types, tests and build;
the Compose stack from a clean folder with every service healthy; the smoke tests of every endpoint; network
isolation (the frontend cannot resolve `database`); the 429 on the 11th request in a minute; persistence across
`docker compose down` / `up`; idempotent seed (`inserted: 0` on the second run); graceful shutdown log lines.
Each of us has read every file, including the partner's, and can explain why each non-obvious line is there.
