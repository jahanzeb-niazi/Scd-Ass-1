# RUNBOOK

## Deploying

### Local (Docker Compose)
```
cp .env.example .env      # fill in real values
docker compose up -d --build
```
TODO(you): confirm this is genuinely a working one-command quickstart from a
CLEAN clone before you submit — the spec calls out a broken quickstart as an
automatic -5 (§5.3). Test it on a machine (or at least a fresh directory)
that has never had this repo's containers built before.

### Kubernetes (local k3d/kind)
TODO(you): document the actual commands once you've run them for real, e.g.:
```
k3d cluster create civicpulse
kubectl apply -k k8s/overlays/dev
kubectl get pods -n civicpulse -w
```

### Production (CI/CD)
Deploys automatically via `.github/workflows/cd.yml` on push to `main`.
TODO(you): document how to trigger a manual deploy if needed, and where to
find the deployed image SHA (`kubectl get deployment backend -n civicpulse -o
jsonpath='{.spec.template.spec.containers[0].image}'`).

## Rolling back

Two mechanisms (§3.4) — document when you'd actually use each:

**Fast / imperative (the 3am answer):**
```
kubectl rollout undo deployment/backend -n civicpulse
```

**Declarative / auditable (the correct answer once the fire is out):**
TODO(you): document the actual steps — re-apply the previous overlay with the
previous known-good SHA via the same `kustomize edit set image` +
`kubectl apply -k` flow used in cd.yml, but pointed at the prior commit.

## Reading logs

TODO(you): document how to find logs given your structured JSON logging setup
(app/logging_config.py) — e.g.:
```
kubectl logs -n civicpulse deployment/backend --tail=100 -f
```
Note that every log line carries a `request_id` (propagated from the
`X-Request-ID` header) — document how to correlate a user-reported issue back
to a specific request_id if you build any UI surface for that.

## When triage starts failing

TODO(you): walk through the actual diagnostic steps someone should take:
1. Check `GET /api/meta/providers` — is `active_provider` what you expect?
   Are recent outcomes showing `fallback: true`?
2. Check backend logs for `triage_fallback` WARNING lines (see
   app/logging_config.py) — the error_class field tells you what failed.
3. TODO(you): what's the actual remediation for a Groq rate-limit vs. an
   invalid API key vs. a network partition (internal: true network issue)?
   Write the real steps once you've actually hit each of these once.
