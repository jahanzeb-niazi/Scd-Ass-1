# ADR 0002: Frontend Runtime Configuration

## Status
TODO(you): Proposed / Accepted

## Context
TODO(you): Explain the build-once-deploy-many problem in your own words
(§2.1): Vite bakes `import.meta.env` values into static JS at BUILD time, so
if the backend URL were read that way, the built image would be
environment-specific.

## Decision
TODO(you): State which option you implemented — see the TODOs already left in
frontend/src/config.ts and frontend/nginx.conf:
  - Option A: `/config.js` generated at container start from env vars
  - Option B: nginx proxies `/api` so the frontend never needs an absolute URL
The scaffold defaults to assuming Option B; confirm that's actually what you
built (or switch to A and update this ADR accordingly).

## Consequences
TODO(you): What does your choice mean for local dev vs. Compose vs.
Kubernetes? E.g. if you chose B, does Vite's dev server (`npm run dev`) also
need a proxy config, or only nginx in the built image?

## Alternatives considered
TODO(you): Address why you didn't just accept the environment-specific-image
trade-off (i.e. build a separate image per environment) — this is a real
alternative, just one the assignment explicitly wants you to reject and explain why.
