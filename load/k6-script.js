/**
 * Load generator for the HPA demo (§3.3): "install metrics-server, then
 * generate load with k6 or hey and capture the scale-out."
 *
 * Run against the Ingress host once deployed, e.g.:
 *   k6 run --vus 50 --duration 5m load/k6-script.js
 *
 * TODO(you): tune vus/duration to actually push backend CPU past the HPA's
 * 60% averageUtilization threshold — too gentle a load and you'll never see
 * a scale-out event to capture in `kubectl get hpa -w`.
 */
import http from "k6/http";
import { check, sleep } from "k6";

// TODO(you): replace with your actual Ingress host (see k8s/base/ingress.yaml)
const BASE_URL = __ENV.BASE_URL || "http://civicpulse.local";

const SAMPLE_TEXTS = [
  "Burst water main flooding Street 12 since fajr, water entering ground floors",
  "Streetlight outage on Main Boulevard for the past week, unsafe at night",
  // TODO(you): add more variety — reuse a few of scripts/seed.py's sample complaints
];

export const options = {
  // TODO(you): pick a shape that actually demonstrates scale-out AND
  // scale-in (e.g. a ramp: stages: [{duration:'2m', target:50}, {duration:'3m', target:50}, {duration:'2m', target:0}])
  vus: 20,
  duration: "3m",
};

export default function () {
  const text = SAMPLE_TEXTS[Math.floor(Math.random() * SAMPLE_TEXTS.length)];
  const payload = JSON.stringify({
    text,
    location: "Load Test District",
  });

  const res = http.post(`${BASE_URL}/api/complaints`, payload, {
    headers: { "Content-Type": "application/json" },
  });

  check(res, {
    "status is 201 or 429": (r) => r.status === 201 || r.status === 429,
    // 429 is EXPECTED once the rate limiter kicks in — don't treat it as a
    // load-test failure, it's your Redis rate limiter doing its job (§2.4).
  });

  sleep(1);
}

// TODO(you): after the run, screenshot/export the k6 summary alongside your
// `kubectl get hpa -w` capture, and build the replicas-vs-load chart required
// by the rubric (§3.3, H — "a chart of replicas against offered load over time").
