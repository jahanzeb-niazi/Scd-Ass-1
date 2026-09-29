# CivicPulse runbook

Operational procedures. Every command here is meant to be copy-pasted.

## 1. Deploy

### Local, Docker Compose

```bash
cp .env.example .env               # first time only; add GEMINI_API_KEY if you have one
docker compose up -d --build       # migrate + seed run once, then backend, then frontend
open http://localhost:8080         # frontend   ·   http://localhost:8000/docs  API docs
```

Optional profiles: `--profile ollama` (offline LLM, then set `TRIAGE_PROVIDER=ollama`) and
`--profile observability` (Prometheus :9090, Grafana :3000).

### Production images with Compose

```bash
IMAGE_REPO=ghcr.io/<owner>/civicpulse IMAGE_TAG=<full-commit-sha> \
  docker compose -f compose.prod.yaml up -d
```

### Kubernetes (local k3d)

```bash
./scripts/k8s-up.sh                # cluster + images + VPA + secret + dev overlay
open http://civicpulse.localhost:8081
```

### Kubernetes (CI)

Merging to `main` runs `cd.yml`: test → build-push (SHA tag, digest, SBOM, Cosign) →
deploy-k8s (verify signature, pin digests, apply, migrate, rollout, smoke test).

## 2. Roll back

| Situation | Use | Command |
|---|---|---|
| **3 a.m., something is on fire** | imperative, ~30 s | `kubectl -n civicpulse rollout undo deployment/backend` (add `--to-revision=N` from `kubectl rollout history`) |
| **Fire is out, make it permanent** | declarative, auditable | re-apply the previous overlay with the previous SHA/digest (below) |

Declarative rollback — the cluster matches a commit again, and the rollback is itself in Git:

```bash
PREV=<previous good commit sha>
cd k8s/overlays/prod
kustomize edit set image \
  civicpulse-backend=ghcr.io/<owner>/civicpulse-backend:${PREV} \
  civicpulse-frontend=ghcr.io/<owner>/civicpulse-frontend:${PREV}
kubectl apply -k .
kubectl -n civicpulse rollout status deploy/backend
```

(or `git revert` the bad commit and let `cd.yml` redeploy). `rollout undo` leaves the cluster
disagreeing with Git; always follow it with the declarative step.

**Migrations:** rollback is code-only. Migrations must be backward compatible with the
previous release (expand → migrate → contract). To undo a migration deliberately:
`kubectl -n civicpulse exec deploy/backend -- alembic downgrade -1`.

## 3. Read logs

Logs are JSON lines on stdout with a `request_id` on every line.

```bash
docker compose logs -f backend                                   # Compose
kubectl -n civicpulse logs -f deploy/backend --all-containers     # k8s (one pod)
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=200 --prefix  # all pods

# follow one request end to end
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=-1 | grep '"request_id": "abc123"'

# only triage fallbacks
kubectl -n civicpulse logs -l app.kubernetes.io/name=backend --tail=-1 | jq -c 'select(.message=="triage fallback to rules")'
```

Send `X-Request-ID: <your-id>` on a request to find it later; the response echoes it.

## 4. When triage starts failing

Symptom: complaints show `triaged_by = rules:fallback`; Stats page shows fallback rows;
`civicpulse_triage_fallback_total` rising. **Citizens are unaffected** — submissions still
return 201 with a rules-based classification. This is degraded quality, not an outage.

1. **Which error?** `curl -s localhost:8000/api/meta/providers | jq '.recent[] | {provider, error, latency_ms}'`
   (k8s: via the Ingress at `/api/meta/providers`).
2. **By error class:**
   | error | meaning | action |
   |---|---|---|
   | `ProviderUnavailableError` | no key, or network/DNS failure | check the Secret has `GEMINI_API_KEY`; from a backend pod: `python -c "import httpx;print(httpx.get('https://generativelanguage.googleapis.com').status_code)"` |
   | `ProviderRateLimitedError` | Gemini 429: free-tier quota exhausted | check AI Studio usage; lower `RATE_LIMIT_REQUESTS`; wait for the quota window; or switch provider (below) |
   | `ProviderTimeoutError` | > 10 s per attempt | provider slow; check Google status; consider a smaller model (`GEMINI_MODEL`) |
   | `ProviderServerError` | Gemini 5xx | provider incident; nothing to fix locally |
   | `ProviderRequestError` | 400/401/403/404 | bad/revoked key or wrong `GEMINI_MODEL` name — not retried, fix config |
   | `ProviderOutputError` | model returned non-schema output | check model name; a model change can break JSON mode |
3. **Switch provider without a code change:**
   ```bash
   kubectl -n civicpulse patch configmap civicpulse-config --type merge -p '{"data":{"TRIAGE_PROVIDER":"rules"}}'
   kubectl -n civicpulse rollout restart deploy/backend
   ```
   Compose: set `TRIAGE_PROVIDER` in `.env`, then `docker compose up -d backend`.
4. **Rotate a leaked key:** revoke it in AI Studio, create a new one, then
   `kubectl -n civicpulse create secret generic civicpulse-secrets --from-literal=... --dry-run=client -o yaml | kubectl apply -f -`
   and `rollout restart deploy/backend`. Update the GitHub Secret `GEMINI_API_KEY`.

## 5. Other checks

```bash
curl -s localhost:8000/ready | jq        # 503 names the failed dependency
kubectl -n civicpulse get hpa -w          # autoscaling
kubectl -n civicpulse describe vpa backend-vpa   # right-sizing recommendation
kubectl -n civicpulse get pvc             # pgdata-postgres-0, redisdata
```
