# ADR 0002 — Frontend runtime configuration: nginx proxies `/api`

**Status:** Accepted · **Date:** 2026-09-27

## Context

Vite replaces `import.meta.env.*` at **build time**. If the API URL were baked into the
bundle, the frontend image would be environment-specific and build-once-deploy-many would
be broken for the frontend. The spec offers two remedies: a `/config.js` generated at
container start, or proxying `/api` through nginx.

## Decision

**The browser only ever calls the relative path `/api`. nginx proxies it to the backend.**

- `frontend/src/api/client.ts` uses same-origin requests; there is no API URL, and no
  `VITE_*` variable, anywhere in the bundle.
- `frontend/nginx.conf` is an envsubst template. The official nginx image renders it at
  container start; `BACKEND_UPSTREAM` (e.g. `backend:8000`) is the only runtime input.
- In development, Vite's dev server proxies `/api` the same way
  (`API_PROXY_TARGET`, read by Node only, never shipped).
- On Kubernetes the Ingress routes `/api` straight to the backend Service; the nginx proxy
  is then simply unused. Same image either way.

## Alternatives considered

- **`/config.js` at start** — works, but the browser then calls the backend cross-origin,
  which requires CORS configuration per environment and exposes the backend host to clients.
  It also adds a blocking script before the app can boot.

## Consequences

- One image, any environment. Nothing to rebuild per deploy.
- No CORS in production: browser and API share an origin. (`CORS_ORIGINS` exists in the
  backend only for ad-hoc cross-origin development and is empty by default.)
- nginx must set `X-Forwarded-For`; the backend rate limiter trusts only the right-most entry
  (the proxy's own view of the client), so a client cannot spoof its way past the limit.
- nginx's timeout for `/api` (30 s) must exceed worst-case triage (10 s + retry + 10 s).
