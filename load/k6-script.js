// CivicPulse load test (k6).
//
//   HPA scale-out (rubric H, ENGINEERING-NOTES Q5):
//     k6 run --out csv=docs/evidence/k6-results.csv load/k6-script.js
//
//   Zero-downtime rolling update (bonus +4) — run this, then in another terminal
//   `kubectl -n civicpulse set image deploy/backend backend=<new image>`:
//     k6 run -e SCENARIO=rollout load/k6-script.js
//
// Only read endpoints are exercised: POST /api/complaints is rate-limited to
// 10/min/IP by design and would spend LLM quota, so it is not a load target.
import http from "k6/http";
import { check } from "k6";

// Target the k3d load balancer by IP and send the Ingress host as a header, so
// no DNS for *.localhost is needed (k6 is a Go binary; Windows/Linux differ there).
const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8081";
const HOST = __ENV.HOST_HEADER || "civicpulse.localhost";
const PARAMS = { headers: { Host: HOST } };
const SCENARIO = __ENV.SCENARIO || "hpa";

const scenarios = {
  // Offered load steps up, holds, then drops — so the chart shows both the
  // scale-out lag and the slow (300 s stabilisation) scale-in.
  hpa: {
    executor: "ramping-arrival-rate",
    startRate: 5,
    timeUnit: "1s",
    preAllocatedVUs: 50,
    maxVUs: 400,
    stages: [
      { target: 5, duration: "1m" },    // baseline
      { target: 80, duration: "1m" },   // ramp
      { target: 80, duration: "4m" },   // sustained: watch replicas climb
      { target: 5, duration: "1m" },    // drop
      { target: 5, duration: "5m" },    // observe slow scale-down
    ],
  },
  // Steady traffic across a `kubectl set image`: every request must succeed.
  rollout: {
    executor: "constant-arrival-rate",
    rate: 20,
    timeUnit: "1s",
    duration: __ENV.DURATION || "3m",
    preAllocatedVUs: 20,
    maxVUs: 100,
  },
};

export const options = {
  scenarios: { [SCENARIO]: scenarios[SCENARIO] },
  thresholds:
    SCENARIO === "rollout"
      ? { http_req_failed: ["rate==0"], checks: ["rate==1"] } // zero failed requests
      : { http_req_failed: ["rate<0.01"] },
};

const FILTERS = ["", "&priority=high", "&status=open", "&category=water", "&category=roads"];

export default function () {
  const f = FILTERS[Math.floor(Math.random() * FILTERS.length)];
  const list = http.get(`${BASE_URL}/api/complaints?page_size=100${f}`, {
    ...PARAMS,
    tags: { endpoint: "list" },
  });
  check(list, { "list 200": (r) => r.status === 200 });

  if (Math.random() < 0.2) {
    const stats = http.get(`${BASE_URL}/api/stats`, { ...PARAMS, tags: { endpoint: "stats" } });
    check(stats, { "stats 200": (r) => r.status === 200 });
  }
}
