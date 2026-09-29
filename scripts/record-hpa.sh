#!/usr/bin/env bash
# Record HPA state every 5 s while a load test runs, for the replicas-vs-load chart.
#   ./scripts/record-hpa.sh > docs/evidence/hpa-samples.csv      (Ctrl-C to stop)
# Run `kubectl get hpa -n civicpulse -w | tee docs/evidence/hpa-watch.txt` alongside
# it for the raw -w capture the submission asks for.
set -euo pipefail
NS=civicpulse
echo "epoch_s,current_replicas,desired_replicas,cpu_utilisation_pct"
while true; do
  line=$(kubectl -n "$NS" get hpa backend-hpa -o \
    jsonpath='{.status.currentReplicas},{.status.desiredReplicas},{.status.currentMetrics[0].resource.current.averageUtilization}' \
    2>/dev/null || echo ",,")
  echo "$(date +%s),${line}"
  sleep 5
done
