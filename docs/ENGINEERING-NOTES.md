# Engineering notes

Answers to the eight questions in §5.2, plus the justifications the spec asks for elsewhere.
References are `file:line` in this repository.

Every number below comes from running this code (the command is given next to it); where something could not be
measured we say so instead of estimating. Raw outputs are in `docs/evidence/`.

---

## Q1 — Three things that differ between a laptop and a CI runner, and the line that freezes each

| # | What differs | Where it bites | Frozen by |
|---|---|---|---|
| 1 | **Python / Node version.** A laptop has whatever Python/Node was installed; `ubuntu-24.04` ships its own. | `StrEnum`, `datetime.UTC` (3.11+), Vite 8 needs Node ≥ 20. | `backend/Dockerfile:7` `ARG PYTHON_IMAGE=python:3.12-slim`, `frontend/Dockerfile:6` `FROM node:22-alpine`; CI pins the same in `.github/workflows/ci.yml:17-18`. |
| 2 | **Dependency versions.** `pip install fastapi` on two machines a week apart resolves different trees. | A minor release of FastAPI/SQLAlchemy changes behaviour. | Exact pins in `backend/requirements.txt:2-11`, installed at `backend/Dockerfile:17`; `frontend/package-lock.json` (lockfileVersion 3) installed with `npm ci` at `frontend/Dockerfile:10`. |
| 3 | **Timezone.** Our laptops run Asia/Karachi (UTC+5); the runner and containers run UTC. | The database session inherited the host zone and returned `+05:00` timestamps on a laptop but `Z` in CI — the spec requires UTC. | `backend/app/repositories/database.py:22` pins every DB session to `timezone=UTC`; the column type is `timestamptz` (`backend/alembic/versions/0001_initial_schema.py`). |

## Q2 — Where the pipeline sits on the CI/CD maturity ladder (Lecture 03, slide 32)

The ladder, bottom to top: manual build and deploy → continuous integration → continuous delivery →
continuous deployment → progressive delivery / GitOps.

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

**Status: not measured.** We could not run the load test on a local cluster (see Q8: the k3d cluster on our
Windows laptops could not pull images from inside its nodes, so the VPA recommender and the data services never
became ready). We are not going to invent a number. The HPA manifest itself is exercised on every merge to `main`:
`cd.yml` (deploy-k8s) applies `k8s/overlays/prod` to an ephemeral k3d cluster and waits for rollout, so the object is
valid and admitted — but no load is offered there, so it gives no lag figure.

**Where the time would go, from our manifests and the controller defaults** (these are the terms a measurement would
be split into; the procedure is `scripts/record-hpa.ps1` + `load/k6-script.js` + `scripts/hpa_chart.py`):
1. **Metrics pipeline** — metrics-server scrapes each kubelet on an interval (k3s ships a 15 s resolution) and CPU
   is a rate over a window, so the HPA sees a rise one to two scrapes late: roughly 15–30 s.
2. **HPA sync period** — the controller re-evaluates every 15 s (kube-controller-manager default):
   0–15 s more before it acts on the new number.
3. **Pod start** — scheduling, container start, the `startupProbe` on `/health`, then the `readinessProbe` on
   `/ready` (`k8s/base/backend.yaml`) must pass before the Service sends traffic. With the image already on the node
   this is a few seconds; with an image pull it is dominated by the pull.
4. **Scale-up policy** — `stabilizationWindowSeconds: 0` (`k8s/base/hpa.yaml:23`) adds nothing on the way up;
   the 300 s window applies only to scale-down.

So the expected order of magnitude is **30–60 s** from offered load rising to a new pod taking traffic — an
expectation from defaults, not a measurement.

**What would reduce it:** a shorter metrics-server resolution; requests sized so utilisation crosses 60 % sooner;
a smaller image and faster start (images pre-pulled on nodes); `minReplicas` sized for the known daily peak; or
scaling on a leading signal (request rate via KEDA / custom metrics) instead of lagging CPU. **This lag is why
autoscaling is not capacity planning:** whatever the first half-minute of a spike needs must already be running.

## Q6 — Why VPA is in Off mode

`k8s/base/vpa.yaml:18` — `updateMode: "Off"`. HPA scales replica count on **CPU utilisation =
usage ÷ request** (`k8s/base/hpa.yaml:18`, request at `k8s/base/backend.yaml:76`). VPA in Auto mode changes that
same request. The loop: load rises → VPA raises the CPU request → the same usage is now a smaller percentage →
HPA scales **in** → fewer pods carry the load, per-pod usage rises → VPA raises the request again → … Pods are
also evicted to apply each new request, adding churn during exactly the moments of high load. With both on CPU
the two controllers fight over one signal. Recommender mode plus a human decision (copy Target into
`backend.yaml`, re-run the load test) is the current industrial practice.

**Recommendation loop — status: not run.** The VPA object and the recommender install are in the repo
(`k8s/base/vpa.yaml`, `scripts/install-vpa.ps1`), but without a working local cluster under load (Q8) there is no
recommendation to commit, so the requests are still the initial guesses:

| | CPU request | Memory request |
|---|---|---|
| Guessed (initial manifest, `k8s/base/backend.yaml`) | 100m | 128Mi |
| VPA Target | not measured | not measured |

The intended loop, unchanged: run the load test, `kubectl -n civicpulse describe vpa backend-vpa >
docs/evidence/vpa-recommendation.txt`, copy **Target** into `backend.yaml` through a PR, re-run the test.
**Expected effect on the HPA:** if the Target raises the CPU request, the same usage is a lower percentage of it,
so the HPA scales out later and to fewer replicas under the same load (and the reverse if it lowers it) — which is
exactly why the request is changed by a person between runs and never by VPA in Auto next to a CPU HPA.

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

**Bringing the stack up on a local k3d cluster from Windows PowerShell cost us an evening, in three layers.**

**Symptom 1.** `.\scripts\k8s-up.ps1` stopped at the very first step with
`k3d : FATA[0000] No nodes found for given cluster` (NativeCommandError), and every `kubectl` command afterwards
printed `memcache.go:265 ... invalid character '<' looking for beginning of value`.
**What we believed first:** k3d was broken or a half-created cluster was stuck, so we deleted and recreated it and
pulled the k3s images by hand. **The truth:** `k3d cluster list` printed an empty table — there was simply no cluster
yet, which is the normal first-run state. The script checked existence with `k3d cluster list $Cluster *> $null`;
under `$ErrorActionPreference = "Stop"` Windows PowerShell turns a native command's stderr line into a terminating
error, so the script died *before* the `$LASTEXITCODE` check that would have created the cluster. The `'<'` error was
a stale kube-context pointing at something that answered with HTML. **Fix:** check with `k3d cluster list -o json`,
which writes nothing to stderr (`scripts/k8s-up.ps1:44`), and re-merge the kubeconfig after creation.
The next run failed with `Cannot validate argument on parameter 'PipelineVariable'` — our `Invoke-Native` helper was
an *advanced* function, so PowerShell bound k3d's `-p` flag to its own `-PipelineVariable` common parameter; it is now
a simple function (`scripts/k8s-up.ps1:21`).

**Symptom 2.** The cluster came up, then `kubectl apply` for the VPA CRD failed.
**The exact line that told us the truth:**
`failed to download openapi: Get "https://host.docker.internal:57777/openapi/v2?timeout=32s": dial tcp 172.17.12.231:57777: connectex: A connection attempt failed`.
k3d had written `https://host.docker.internal:<port>` into our kubeconfig, and on our laptop that name resolves to an
address that is not reachable from the host. The API port is published on loopback, so the fix is to point kubectl at
`127.0.0.1` on the same port (`scripts/k8s-up.ps1:60-64`); the k3s certificate already covers 127.0.0.1.

**Symptom 3 — where we stopped.** `deploy/vpa-recommender` never became available:
`error: timed out waiting for the condition`. The nodes pull `registry.k8s.io` and Docker Hub images themselves, and
from our network those pulls time out (the same `TLS handshake timeout` we had seen from Docker Desktop earlier, which
we had worked around with a registry mirror that the k3d nodes do not use). We changed the script to pull third-party
images on the host and `k3d image import` them (`scripts/k8s-up.ps1:75-77`), but ran out of time to complete the HPA
and VPA measurements locally — which is why Q5 and Q6 report no numbers. The same manifests deploy fine on the GitHub
runner in `cd.yml`, whose network has no such restriction.

**What we learned:** read the *first* error literally before theorising (the empty `k3d cluster list` was the answer),
and on Windows treat every native command's stderr as a potential exception in scripts that set `Stop`.

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

### Build context and image sizes (§3.1)
Measured with `scripts/context-size.sh` (BuildKit copies the context into a scratch stage and we measure what it
actually received), on a working copy after `npm ci` and a test run — i.e. with `node_modules` and caches present, as
on a developer laptop.

| Context | Without .dockerignore | With .dockerignore | Reduction |
|---|---|---|---|
| backend | 648 KiB | 244 KiB | 62 % (tests, caches, `openapi.json` excluded) |
| frontend | 227,704 KiB (≈ 222 MiB) | 296 KiB | 99.9 % (`node_modules` alone is ≈ 222 MiB) |

Without the frontend `.dockerignore`, every build would send ~222 MiB to the daemon and `COPY . .` would overwrite the
Linux `node_modules` from `npm ci` with the host's (Windows) copy.

Image sizes, from `docker image ls` after `docker compose build` on our machine:

| Image | Size | Note |
|---|---|---|
| civicpulse-backend:dev | **56** | python:3.12-slim + venv, no compilers (builder stage discarded) |
| civicpulse-frontend:dev | **21** | nginx:1.27-alpine + static files only; the node toolchain stays in the build stage |
