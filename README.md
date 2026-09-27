# CivicPulse

Municipal complaint intake, AI triage and operations. A citizen describes a problem in their
own words; the system classifies it into a category, a priority and a one-line summary with
an LLM, stores it durably, and puts it on an operator dashboard — and keeps working when the
LLM is slow, rate-limited or wrong.

> **Status:** backend and frontend complete and tested. Docker/Compose, Kubernetes and CI/CD
> (rubric sections G–I) are the next phase.

```mermaid
flowchart LR
  U[Citizen / Operator] -->|HTTP| FE[frontend<br/>React + Vite → nginx]
  FE -->|/api proxied| BE[backend<br/>FastAPI + Pydantic]
  BE --> PG[(PostgreSQL 16)]
  BE --> RD[(Redis 7<br/>cache + rate limiter)]
  BE --> TP{{TriageProvider}}
  TP -->|default| LLM[Gemini · JSON mode]
  TP -->|CI| SIM[SimulatedTriage]
  LLM -. timeout · 429 · bad JSON .-> RB[RuleBasedTriage · fallback]
```

## Run it locally (without Docker, for now)

Prerequisites: Python 3.12, Node 22, a PostgreSQL 16 and a Redis 7 you can reach.

```bash
cp .env.example .env            # then edit; GEMINI_API_KEY may stay empty

# --- backend ---
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://civicpulse:change-me@localhost:5432/civicpulse
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head            # schema is owned by migrations, never by app startup
python -m app.seed              # 33 complaints; safe to run again (inserts 0)
python -m app                   # http://localhost:8000  ·  docs at /docs

# --- frontend (second terminal) ---
cd frontend
npm ci
npm run dev                     # http://localhost:5173  (proxies /api → :8000)
```

With no `GEMINI_API_KEY`, every complaint is triaged by `rules:fallback` — visible on the
Stats page and at `/api/meta/providers`. Nothing returns a 500.

## Checks

```bash
# backend (tests need a PostgreSQL; set TEST_DATABASE_URL, default …/civicpulse_test)
cd backend && ruff check . && ruff format --check . && mypy && pytest --cov

# frontend
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
npm run check:api               # typed client still matches backend/openapi.json
```

Regenerate the typed client after changing the API:
`cd backend && python -m app.export_openapi > openapi.json && cd ../frontend && npm run gen:api`

## API

| Method | Path | Behaviour |
|---|---|---|
| POST | `/api/complaints` | Validate → triage → persist. **201**; **400** field-level errors; **429** + `Retry-After` (10/min/IP, Redis). |
| GET | `/api/complaints/{id}` | **200** / **404** (bad UUID → 400). |
| GET | `/api/complaints` | Filters `category`, `priority`, `status`; `page`, `page_size ≤ 100`; returns `total`. Newest first. |
| PATCH | `/api/complaints/{id}/status` | State machine; invalid → **409** naming the transition. |
| GET | `/api/stats` | Counts by category/priority/status. Redis, TTL 30 s, invalidated on write. `X-Cache: HIT\|MISS`. |
| GET | `/api/meta/providers` | Active provider, model, triage-cache hit rate, last 20 outcomes. |
| GET | `/health` | Liveness. Touches nothing external. |
| GET | `/ready` | Readiness. 200 only if Postgres **and** Redis reachable (and not draining); 503 names the failure. |
| GET | `/metrics` | Prometheus: requests, latency histogram, triage latency, fallback counter. |

Status machine: `open → in_progress → resolved`, `open → rejected`, `in_progress → rejected`;
`resolved` and `rejected` are terminal. Every complaint response carries
`allowed_transitions`, so the frontend never duplicates the table.

## Layout

```
backend/app/
  routes/        HTTP only — parse, validate, serialise, status codes
  services/      business rules — triage policy, state machine, stats, rate-limit policy
  repositories/  persistence — all SQL lives here
  providers/     outbound integrations behind interfaces — triage/, cache, rate limiter
  container.py   composition root;  deps.py  per-request wiring (routes never see a session)
frontend/src/
  api/           generated schema.d.ts + typed client
  pages/         Submit, Dashboard, Stats
  components/    ErrorBoundary, badges, spinner
```

## Decisions

- [ADR 0001 — Triage behind a provider interface (Gemini)](docs/adr/0001-provider-interface.md)
- [ADR 0002 — Frontend runtime config: nginx proxies `/api`](docs/adr/0002-frontend-runtime-config.md)
- ADR 0003 — Deploy by SHA *(CI/CD phase)*
- [ADR 0004 — PII: body-only, redacted, never the contact](docs/adr/0004-pii-and-data-governance.md)
