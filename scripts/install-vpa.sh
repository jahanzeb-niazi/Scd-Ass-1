#!/usr/bin/env bash
# Install the Vertical Pod Autoscaler in recommender-only mode: CRD, RBAC and the
# recommender. No updater and no admission controller — with updateMode "Off"
# nothing ever evicts or mutates pods. Idempotent.
set -euo pipefail
VPA_VERSION="${VPA_VERSION:-1.8.0}"
BASE="https://raw.githubusercontent.com/kubernetes/autoscaler/vertical-pod-autoscaler-${VPA_VERSION}/vertical-pod-autoscaler/deploy"

kubectl apply -f "${BASE}/vpa-v1-crd-gen.yaml"
if [ "${CRD_ONLY:-false}" = "true" ]; then
  exit 0
fi
kubectl apply -f "${BASE}/vpa-rbac.yaml"
kubectl apply -f "${BASE}/recommender-deployment.yaml"
kubectl -n kube-system rollout status deploy/vpa-recommender --timeout=180s
