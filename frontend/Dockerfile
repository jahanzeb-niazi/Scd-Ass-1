# syntax=docker/dockerfile:1
# TODO(you): pin these to digests for the bonus (§3.1)
FROM node:22-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json* ./
# TODO(you): once package-lock.json exists (after a real `npm install`),
# switch this to `npm ci` for reproducible builds.
RUN npm install

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

# Node/node_modules/source never reach this stage — report both stage sizes
# in your README/notes (§2.1: "a frontend image over ~60 MB means the
# multi-stage split is not doing its job").
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# TODO(you): nginx's stock image runs as root by default. For the non-root
# requirement (§3.1), either switch to the "unprivileged" nginx image variant
# or reconfigure nginx to run on a high port as a non-root user — decide and
# document which, then update this Dockerfile and any K8s securityContext to match.

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
