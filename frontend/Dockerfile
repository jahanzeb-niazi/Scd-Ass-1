# syntax=docker/dockerfile:1.7
# CivicPulse frontend — Node builds, nginx serves. The final image contains
# no Node, no node_modules and no source: only static files and nginx.

# ------------------------------------------------------------------ build
FROM node:22-alpine AS build
WORKDIR /src

# Update all packages to fix security vulnerabilities
RUN apk update && apk upgrade

# Dependencies first (cache-friendly): only a lockfile change re-runs npm ci.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
# No VITE_* variables: the bundle only calls the relative path /api (ADR 0002).
RUN npx tsc --noEmit -p tsconfig.json && npx vite build

# ------------------------------------------------------------------ serve
FROM nginx:1.27-alpine AS runtime
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="civicpulse-frontend" \
      org.opencontainers.image.source="https://github.com/OWNER/civicpulse" \
      org.opencontainers.image.revision="${GIT_SHA}"

# Update all packages to fix security vulnerabilities (including zlib CVE-2026-22184)
RUN apk update && apk upgrade

# Run as the unprivileged `nginx` user (uid 101): move the pid file to /tmp,
# drop the `user` directive, and let nginx own the dirs it writes at runtime
# (the envsubst step renders templates into /etc/nginx/conf.d at start-up).
RUN sed -i -e 's|^pid .*|pid /tmp/nginx.pid;|' -e '/^user /d' /etc/nginx/nginx.conf \
 && rm -f /etc/nginx/conf.d/default.conf \
 && chown -R nginx:nginx /var/cache/nginx /etc/nginx/conf.d

# Runtime configuration: rendered by the image's entrypoint from environment
# variables when the container starts — one image, every environment.
ENV BACKEND_UPSTREAM=backend:8000
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html

USER 101:101
EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]

CMD ["nginx", "-g", "daemon off;"]
