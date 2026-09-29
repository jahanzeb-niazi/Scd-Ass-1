#!/usr/bin/env bash
# Build-context size with and without .dockerignore, for ENGINEERING-NOTES / rubric G.
#   ./scripts/context-size.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

size_without() { du -sk "$1" | awk '{print $1}'; }

size_with() {
  # Ask BuildKit what it actually transfers: a throwaway stage that copies the
  # whole context, then measure it.
  local dir=$1 tmp
  tmp=$(mktemp -d)
  printf 'FROM scratch\nCOPY . /ctx\n' > "$tmp/Dockerfile"
  docker buildx build -q --no-cache -f "$tmp/Dockerfile" --output "type=local,dest=$tmp/out" "$dir" >/dev/null
  du -sk "$tmp/out/ctx" | awk '{print $1}'
  rm -rf "$tmp"
}

printf '%-10s %14s %14s\n' context "without (KiB)" "with (KiB)"
for c in backend frontend; do
  printf '%-10s %14s %14s\n' "$c" "$(size_without "$ROOT/$c")" "$(size_with "$ROOT/$c")"
done
echo
echo "Image sizes (after docker compose build):"
docker image ls --format '{{.Repository}}:{{.Tag}}  {{.Size}}' | grep -E '^civicpulse-(backend|frontend)' || true
