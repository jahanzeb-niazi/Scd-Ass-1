# Evidence

Screenshots and captures the rubric asks for. File names below are what the README,
ENGINEERING-NOTES and the submission refer to — keep them.

| File | Rubric | How to capture |
|---|---|---|
| `branch-protection.png` | A (3) | Settings → Branches → rule for `main`: PR required, 1 approval, required checks, no direct push |
| `merge-conflict-markers.png`, `merge-conflict-resolved.png` | A (3) | the conflicting file with `<<<<<<<` markers; the resolved diff; the merge commit (`git log --graph`) |
| `conflict-notes.md` | A (3) | 2–4 sentences: why the chosen version won |
| `blocked-merge-red.png` | I (1) | PR with a deliberately failing test: red check + disabled merge button |
| `blocked-merge-green.png` | I (1) | same PR after the fix: green |
| `network-isolation.png` | G (4), video | `docker compose exec frontend ping database` failing (also `getent hosts database`) |
| `hpa-watch.txt` | H (4) | `kubectl -n civicpulse get hpa -w \| tee docs/evidence/hpa-watch.txt` during the load test |
| `hpa-samples.csv`, `k6-results.csv` | H (4) | `scripts/record-hpa.sh`, `k6 run --out csv=…` |
| `hpa-scaling.png` | H (4) | `python scripts/hpa_chart.py docs/evidence/k6-results.csv docs/evidence/hpa-samples.csv` |
| `vpa-recommendation.txt` | H (3) | `kubectl -n civicpulse describe vpa backend-vpa > docs/evidence/vpa-recommendation.txt` |
| `rollout-zero-downtime.txt` | bonus +4 | k6 `SCENARIO=rollout` summary showing `http_req_failed 0.00%` during `kubectl set image` |
| `grafana-dashboard.png` | bonus +2 | Grafana "CivicPulse — API & AI triage" dashboard with traffic |
| `cd-run.png` | I, submission | the successful cd.yml run (test → build-push → deploy-k8s) |
| `ghcr-packages.png` | submission | both packages in GHCR showing SHA tags |
| `persistence-compose.png`, `persistence-k8s.png` | D | row count before/after `docker compose down && up`; before/after `kubectl delete pod postgres-0` |
