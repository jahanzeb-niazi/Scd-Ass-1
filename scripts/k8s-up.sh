#!/usr/bin/env bash
# One command to put CivicPulse on a local k3d cluster (dev overlay, seeded).
#   ./scripts/k8s-up.sh
# Then open http://civicpulse.localhost:8081
set -euo pipefail

CLUSTER="${CLUSTER:-civicpulse}"
NS=civicpulse
PORT="${INGRESS_PORT:-8081}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for bin in docker k3d kubectl; do
  command -v "$bin" >/dev/null || { echo "missing: $bin" >&2; exit 1; }
done

[ -f .env ] || cp .env.example .env
set -a
# shellcheck disable=SC1091
. ./.env
set +a

echo "==> cluster"
if ! k3d cluster list "$CLUSTER" >/dev/null 2>&1; then
  # k3d ships Traefik (ingress) and metrics-server (needed by the HPA).
  k3d cluster create "$CLUSTER" --agents 1 -p "${PORT}:80@loadbalancer" --wait
fi
kubectl config use-context "k3d-${CLUSTER}" >/dev/null

echo "==> images (built once, imported into the cluster nodes)"
docker build -t civicpulse-backend:dev backend
docker build -t civicpulse-frontend:dev frontend
k3d image import civicpulse-backend:dev civicpulse-frontend:dev -c "$CLUSTER"
# Third-party images: pull on the host and import, so nodes never pull from the internet.
THIRD_PARTY="postgres:16-alpine redis:7-alpine registry.k8s.io/autoscaling/vpa-recommender:1.8.0"
# Single-platform tarball: avoids "content digest not found" with the containerd image store.
PLATFORM="linux/$(docker version -f '{{.Server.Arch}}')"
for img in $THIRD_PARTY; do docker pull --platform "$PLATFORM" "$img"; done
TAR="$(mktemp -d)/thirdparty.tar"
# shellcheck disable=SC2086
docker save --platform "$PLATFORM" -o "$TAR" $THIRD_PARTY
k3d image import "$TAR" -c "$CLUSTER"
rm -f "$TAR"

echo "==> VPA (recommender only)"
"$ROOT/scripts/install-vpa.sh" || echo "WARN: VPA recommender not ready yet; the app does not depend on it (updateMode Off)." >&2

echo "==> namespace + secret (from .env, never from a committed file)"
kubectl apply -f k8s/base/namespace.yaml
kubectl -n "$NS" create secret generic civicpulse-secrets \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?set in .env}" \
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "==> apply dev overlay"
existed=$(kubectl -n "$NS" get deploy backend --ignore-not-found -o name)
kubectl -n "$NS" delete job migrate --ignore-not-found   # Jobs are immutable
kubectl apply -k k8s/overlays/dev
kubectl -n "$NS" wait --for=condition=complete job/migrate --timeout=300s
if [ -n "$existed" ]; then
  # Same :dev tag, new image content: force the pods to pick it up.
  kubectl -n "$NS" rollout restart deploy/backend deploy/frontend
fi
kubectl -n "$NS" rollout status deploy/backend --timeout=300s
kubectl -n "$NS" rollout status deploy/frontend --timeout=300s

echo
kubectl -n "$NS" get pods,svc,ingress,hpa
echo
echo "CivicPulse is up:  http://civicpulse.localhost:${PORT}"