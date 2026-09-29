# Engineering notes

Answers to the eight questions in §5.2, plus the justifications the spec asks for elsewhere.
References are `file:line` in this repository.

> **Before submitting:** everything marked **✍ FILL IN** needs *your* measurements or *your*
> experience. The grader and the viva check these against your repo and your video.
> A generic or invented answer scores zero — measure, then write.

---

## Q1 — Three things that differ between a laptop and a CI runner, and the line that freezes each

| # | What differs | Where it bites | Frozen by |
|---|---|---|---|
| 1 | **Python / Node version.** A laptop has whatever Python/Node was installed; `ubuntu-24.04` ships its own. | `StrEnum`, `datetime.UTC` (3.11+), Vite 8 needs Node ≥ 20. | `backend/Dockerfile:7` `ARG PYTHON_IMAGE=python:3.12-slim`, `frontend/Dockerfile:6` `FROM node:22-alpine`; CI pins the same in `.github/workflows/ci.yml:17-18`. |
| 2 | **Dependency versions.** `pip install fastapi` on two machines a week apart resolves different trees. | A minor release of FastAPI/SQLAlchemy changes behaviour. | Exact pins in `backend/requirements.txt:2-11`, installed at `backend/Dockerfile:17`; `frontend/package-lock.json` (lockfileVersion 3) installed with `npm ci` at `frontend/Dockerfile:10`. |
| 3 | **Timezone.** Our laptops run Asia/Karachi (UTC+5); the runner and containers run UTC. | The database session inherited the host zone and returned `+05:00` timestamps on a laptop but `Z` in CI — the spec requires UTC. | `backend/app/repositories/database.py:22` pins every DB session to `timezone=UTC`; the column type is `timestamptz` (`backend/alembic/versions/0001_initial_schema.py`). |

## Q2 — Where the pipeline sits on the CI/CD maturity ladder (Lecture 03, slide 32)

> ✍ **FILL IN:** use the exact rung names from slide 32. The reasoning below maps to the usual ladder
> (manual → CI → continuous delivery → continuous deployment → progressive delivery / GitOps).

**Our rung: continuous deployment to an ephemeral environment.** Every PR runs lint, types,
unit + integration tests, image build, vulnerability scan and manifest validation
(`.github/workflows/ci.yml`), and those checks gate merging. Every merge to `main` rebuilds,
publishes immutable signed images and deploys them automatically with a smoke test
(`.github/workflows/cd.yml:117`, deploy-k8s). No human step between merge and deploy.

**Why not higher:** the deploy target is a throwaway k3d cluster inside the runner, so there is
no long-lived production, no canary or progressive rollout, and no automated rollback on bad
metrics. **Next rung — GitOps / progressive delivery:** a controller (Argo CD / Flux) reconciling a
real cluster from `k8s/overlays/prod`, with canary analysis on the Prometheus metrics we already
export. It buys drift detection, audit of every production change in Git, and automatic
rollback when error rate rises.

## Q3 — The exact line guaranteeing build-once-deploy-many

`.github/workflows/cd.yml:177`

```yaml
"civicpulse-backend=${REPO}/civicpulse-backend@${BACKEND_DIGEST}"
```

The deploy job does not build anything: it pins the overlay to the **digest** the build job
produced and signed (`cd.yml:36` output, verified at `cd.yml:132`). The bytes tested are the bytes
that run. **Without it** — e.g. rebuilding in the deploy job, or deploying `:latest` — a base-image
update or a new dependency release between the two builds ships untested code, and two nodes can
pull two different images during one rollout.

The frontend has a second requirement: `frontend/nginx.conf:42` (`proxy_pass http://${BACKEND_UPSTREAM};`)
plus the relative client in `frontend/src/api/client.ts:33`. Without them, Vite bakes the API URL
into the bundle at build time and the frontend image only works in the environment it was built for.

## Q4 — With a live LLM the service is probabilistic. What does "correct" mean, and how is CI deterministic?

**Correct** is defined on the *contract*, not on the model's opinion:

1. every submission returns 201 and is persisted, whatever the provider does;
2. the stored category/priority are always members of our enums, and the summary is ≤ 140 chars, one line
   (`backend/app/providers/triage/base.py:76`, `parse_triage_json`);
3. the provider is called at most twice, never for > 10 s per attempt, and only retried on timeout/429/5xx
   (`backend/app/services/triage_service.py:110`);
4. every fallback is visible (`triaged_by = rules:fallback`, WARNING log, metric).

Whether Gemini labels a pothole "roads" or "other" is a *quality* property, measured with the hit-rate,
latency and fallback numbers in `docs/TRIAGE.md` — not asserted in CI.

**Determinism by design:** CI pins `TRIAGE_PROVIDER=simulated` (`.github/workflows/ci.yml:74`,
`backend/tests/conftest.py:41`), a seeded fake with no network (`backend/app/providers/triage/simulated.py:35`).
Failure paths use injected fakes — a provider that always raises (`backend/tests/test_fallback.py:30`),
one that returns malformed JSON, one that blocks past the timeout — and retry jitter is set to 0 in tests
(`backend/tests/conftest.py:43`). No test sleeps; the suite has been run repeatedly with identical results.

## Q5 — HPA lag

> ✍ **FILL IN from your own run.** Procedure:
> ```bash
> kubectl -n civicpulse get hpa -w | tee docs/evidence/hpa-watch.txt          # terminal 1
> ./scripts/record-hpa.sh > docs/evidence/hpa-samples.csv                       # terminal 2
> k6 run --out csv=docs/evidence/k6-results.csv load/k6-script.js               # terminal 3
> python scripts/hpa_chart.py docs/evidence/k6-results.csv docs/evidence/hpa-samples.csv
> ```
> `hpa_chart.py` prints the lag between offered load rising and replicas rising.

**Measured lag:** ✍ ___ s (load reached 50 % of peak at t = ___ s; replicas first rose at t = ___ s;
reached ___ replicas at t = ___ s).

**Where the time goes** (write your observed breakdown):
1. **Metrics pipeline** — metrics-server scrapes the kubelet on an interval (k3s default ≈ 15 s) and CPU is
   averaged over a window, so the HPA sees load late. ✍ ___ s
2. **HPA sync period** — the controller evaluates every 15 s by default. ✍ ___ s
3. **Pod start** — scheduling, container start, `startupProbe` on `/health` (`k8s/base/backend.yaml`),
   then `readinessProbe` on `/ready` must pass before the Service sends traffic. ✍ ___ s
4. Scale-up policy: `stabilizationWindowSeconds: 0` (`k8s/base/hpa.yaml:23`) — no added delay here.

**What would reduce it:** a shorter metrics-server resolution; lower requests so utilisation crosses 60 %
sooner; smaller image / faster start; `minReplicas` sized for the known daily peak; or scaling on a leading
signal (request rate via KEDA / custom metrics) instead of lagging CPU. **This lag is why autoscaling is not
capacity planning:** capacity must already exist for the first ✍ ___ s of a spike.

## Q6 — Why VPA is in Off mode

`k8s/base/vpa.yaml:18` — `updateMode: "Off"`. HPA scales replica count on **CPU utilisation =
usage ÷ request** (`k8s/base/hpa.yaml:18`, request at `k8s/base/backend.yaml:76`). VPA in Auto mode changes that
same request. The loop: load rises → VPA raises the CPU request → the same usage is now a smaller percentage →
HPA scales **in** → fewer pods carry the load, per-pod usage rises → VPA raises the request again → … Pods are
also evicted to apply each new request, adding churn during exactly the moments of high load. With both on CPU
the two controllers fight over one signal. Recommender mode plus a human decision (copy Target into
`backend.yaml`, re-run the load test) is the current industrial practice.

**Recommendation loop** ✍ **FILL IN**:

| | CPU request | Memory request |
|---|---|---|
| Guessed (initial manifest) | 100m | 128Mi |
| VPA Lower Bound | | |
| VPA Target | | |
| VPA Upper Bound | | |
| Updated to | | |

Commit the raw output as `docs/evidence/vpa-recommendation.txt` (`kubectl -n civicpulse describe vpa backend-vpa`).
**Effect on HPA after updating requests:** ✍ (e.g. with a larger request, utilisation per pod is lower, so the HPA
scaled out later / to fewer replicas under the same load — quote your numbers).

## Q7 — `internal: true` blocks outbound traffic; where does the LLM call go?

`compose.yaml:232` makes `internal` a network with no route to the outside world. PostgreSQL and Redis live only
there. The backend joins **both** `edge` and `internal` (`compose.yaml:107`); `edge` is an ordinary bridge with
outbound NAT, so the backend's call to `generativelanguage.googleapis.com` (`backend/app/config.py:62`) leaves via
`edge`. The frontend is on `edge` only (`compose.yaml:134`) and cannot resolve or reach `database`
(verified in CI: `.github/workflows/ci.yml`, "Network isolation" step).

**Trade-off accepted:** the component holding the API key and DB credentials also has internet egress. The
alternative — backend on `internal` only, plus a forward proxy on `edge` allow-listing one hostname — is tighter
but adds a moving part; we chose the simpler design and document the risk. The Ollama container also sits on
`edge` because it must pull its model once. On Kubernetes there is no NetworkPolicy by default, so pods have egress;
a production cluster would add an egress policy allowing only the Gemini endpoint.

## Q8 — The failure

> ✍ **FILL IN — this must be your own story.** The viva will ask you about it.
> Structure: **symptom** → **what you wrongly believed first** → **the exact command or log line that told you the truth** → **fix**.
> Example shape (from building this repo — replace with yours):
> *Symptom:* the Redis-outage test took 36 s instead of 3 s. *Believed:* the fake Redis was slow.
> *Truth:* `pytest --durations=4` pointed at one test; redis-py's default `Retry` backs off 3× per command.
> *Fix:* one fast retry (`backend/app/providers/cache.py:34`) — otherwise every request would hang during a Redis blip.

---

## Other justifications required by the spec

### Indexes (§2.3) — each serves a named query
- `ix_complaints_status_priority` (`backend/alembic/versions/0001_initial_schema.py:64`) serves the operator filter
  `GET /api/complaints?status=open&priority=high` — `WHERE status = $1 AND priority = $2`
  (`backend/app/repositories/complaint_repository.py:130`). Status first: it is always present in the triage view.
- `ix_complaints_created_at` (`…0001_initial_schema.py:66`) serves `ORDER BY created_at DESC LIMIT … OFFSET …` on every
  dashboard page load (`complaint_repository.py:141`) via a backward index scan instead of a sort of the whole table.

### Stats cache: why TTL **and** explicit invalidation (§2.4)
Invalidation on write (`backend/app/services/complaint_service.py:96`, `stats_service.py:63`) makes our own writes
visible immediately. The 30 s TTL bounds staleness for writes we did not anticipate: a manual SQL fix, a failed
`DEL` during a Redis blip, a second service writing to the table. Either alone fails one of those cases.

### Why the cache has a volume (Redis AOF) (§2.4)
Our stance: **keep it.** The stats entry is rebuildable, but two other things in Redis are not free to lose:
the rate-limit windows (`backend/app/providers/rate_limiter.py:36`) — losing them on restart lets a burst through
exactly when a restart is most likely — and the 24 h triage cache, whose entries are LLM quota we already spent.
AOF with `everysec` (`compose.yaml:59`) costs at most one second of writes. The counter-argument (a cache should be
disposable) holds for the stats key alone.

### Dev bind mount (§3.2)
`compose.yaml:104` mounts `./backend/app` into the container so `uvicorn --reload` picks up edits — right for
development. It is absent from `compose.prod.yaml`: production must run the exact bytes that were tested and
signed; a bind mount would make the running code whatever happens to be on the host's disk.

### Build context and image sizes (§3.1) ✍ FILL IN
Run `./scripts/context-size.sh` after `docker compose build`.

| Context | Without .dockerignore | With .dockerignore |
|---|---|---|
| backend | | |
| frontend | | |

| Image | Size | Note |
|---|---|---|
| civicpulse-backend | | python:3.12-slim + venv |
| civicpulse-frontend | | must be < ~60 MB: nginx + static files only |
| frontend build stage (node:22-alpine + node_modules) | | `docker build --target build -t fe-build frontend && docker image ls fe-build` |
