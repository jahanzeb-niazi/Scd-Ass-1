# ADR 0003 — Deploy by immutable reference (digest, traceable to the commit SHA)

**Status:** Accepted · **Date:** 2026-09-27

## Context

"What is production running?" must have a one-word answer that can be pasted into
`git show`. A mutable tag such as `:latest` cannot answer it: the same name points at
different bytes over time, two nodes can pull two different images during a rollout, and
rollback to "the previous latest" is meaningless. Build-once-deploy-many also requires that
the bytes tested in CI are the bytes that run.

## Decision

1. `cd.yml` builds each image **once**, after `test` passes (`needs: test`), and pushes it to
   GHCR tagged with the full commit SHA (`${{ github.sha }}`) and `latest`.
   `latest` is a convenience for humans browsing the registry; **it is never deployed**.
2. The push returns the image **digest** (`sha256:…`), captured as a job output.
3. Both digests are **signed with Cosign** (keyless, GitHub OIDC). `deploy-k8s` runs
   `cosign verify`, pinned to this repository's `cd.yml` on `main`, and refuses to deploy an
   unsigned or foreign image.
4. The prod overlay is pinned to the digest:
   `kustomize edit set image civicpulse-backend=ghcr.io/<owner>/civicpulse-backend@sha256:…`
   and every object is annotated `civicpulse.io/git-sha: <sha>`.
5. Images carry the OCI label `org.opencontainers.image.revision=<sha>`.

## Answering "what is production running?"

```bash
kubectl -n civicpulse get deploy backend -o jsonpath='{.metadata.annotations.civicpulse\.io/git-sha}'
# → 3f9c2e1…   then:  git show 3f9c2e1
```

The digest is the byte-level answer; the SHA annotation and the image's `:<sha>` tag map it
back to the commit.

## Consequences

- A digest cannot be moved: rollback means re-deploying the *previous* digest — declarative
  and auditable (see RUNBOOK). `kubectl rollout undo` remains the fast, imperative option.
- Nothing is deployed that CI did not test, build and sign in the same run.
- Compose production follows the same rule with `IMAGE_TAG=<sha>` (`compose.prod.yaml`
  refuses to start without it).
