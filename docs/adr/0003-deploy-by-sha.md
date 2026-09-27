# ADR 0003: Deploy by Commit SHA (Immutable Reference)

## Status
TODO(you): Proposed / Accepted

## Context
TODO(you): Explain why `:latest` is dangerous to deploy (§3.4: "'What is
production running?' must have a one-word answer you can paste into
`git show`"). Note that `:latest` MAY be pushed (cd.yml does push it,
alongside the SHA tag) but must never be the tag a deployment actually
references.

## Decision
TODO(you): Describe how k8s/overlays/prod/kustomization.yaml's
`kustomize edit set image` step (invoked from cd.yml) pins both the backend
and frontend Deployments to `github.sha` at deploy time. Note where the bonus
path (deploy by digest + Cosign signing) would replace SHA with a digest, if
you attempt it.

## Consequences
TODO(you): Rollback implications — `kubectl rollout undo` works regardless,
but re-applying a previous overlay by SHA requires you to actually know which
prior SHA was good. How does your team track that (a deploy log, GitHub
Environments, tags)?

## Alternatives considered
TODO(you): semver tags alone (rejected because a tag is mutable/movable
unless you enforce otherwise), image digests (this is the bonus path — note
why you did or didn't attempt it).
