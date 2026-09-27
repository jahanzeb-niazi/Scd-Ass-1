/**
 * Runtime configuration (§2.1 — "the part most students get wrong").
 *
 * A Vite build bakes import.meta.env values into static JS at BUILD time.
 * If the backend URL were read from import.meta.env, the built image would
 * be environment-specific and you'd lose build-once-deploy-many for the
 * frontend (an automatic problem, though not literally in §5.3's deduction
 * table — treat it as a correctness requirement, not an optional nicety).
 *
 * Pick ONE approach and document it in docs/adr/0002-frontend-runtime-config.md:
 *
 *   Option A — generated /config.js at container start:
 *     A shell script in the frontend Docker image (run from the nginx
 *     entrypoint) writes /usr/share/nginx/html/config.js from environment
 *     variables at `docker run` / pod-start time, e.g.:
 *         window.__CIVICPULSE_CONFIG__ = { apiBaseUrl: "http://actual-host/api" };
 *     index.html loads this script before the bundle (see the TODO there).
 *
 *   Option B — nginx proxies /api, frontend never needs an absolute URL:
 *     nginx.conf proxies requests under /api/ to the backend service, so the
 *     frontend always calls relative path "/api/..." regardless of environment.
 *     This is simpler and is the recommended default — see nginx.conf's TODOs.
 *
 * TODO(you): implement whichever option you choose. This file is written
 * assuming Option B (relative /api path) as the default, since the spec
 * calls it out as viable and it needs no extra container-start scripting —
 * but you MUST make this decision explicitly and write the ADR either way.
 */

declare global {
  interface Window {
    __CIVICPULSE_CONFIG__?: { apiBaseUrl?: string };
  }
}

export const config = {
  // TODO(you): if you choose Option A, read window.__CIVICPULSE_CONFIG__?.apiBaseUrl
  // here instead of hardcoding "/api".
  apiBaseUrl: window.__CIVICPULSE_CONFIG__?.apiBaseUrl ?? "/api",
};
