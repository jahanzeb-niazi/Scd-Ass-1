#!/usr/bin/env python3
"""
scripts/check_submission.py

A lint, not a grader (per the assignment's own description, §5.8): "It
catches the mechanical failures behind most of §5.3. A clean run does not
guarantee a good mark; a dirty run nearly guarantees a bad one."

This implements straightforward, mechanically-checkable heuristics for
several §5.3 items. It does NOT and CANNOT check things that need judgment
(e.g. whether your ADRs are substantive, whether your fallback test is real
rather than vacuous) — those still require your own review before submission.

Run from the repository root:  python scripts/check_submission.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

failures: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_no_env_committed() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        fail(f".env exists at repo root — confirm it is gitignored and was never committed (§5.3: -20)")
    if not (ROOT / ".env.example").exists():
        warn(".env.example is missing — required per §3.2")


def check_unpinned_images() -> None:
    """Best-effort scan for `image:` lines without an explicit tag, and :latest usage."""
    patterns = [
        ("compose.yaml", ROOT / "compose.yaml"),
        ("compose.prod.yaml", ROOT / "compose.prod.yaml"),
    ]
    for label, path in patterns:
        if not path.exists():
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = re.search(r"image:\s*([^\s#]+)", line)
            if not m:
                continue
            image = m.group(1)
            if ":" not in image.split("/")[-1]:
                fail(f"{label}:{lineno} — image `{image}` has no tag (unpinned, §5.3 -8)")
            elif image.endswith(":latest"):
                if label == "compose.prod.yaml":
                    fail(f"{label}:{lineno} — `:latest` must never be deployed (§5.3 -8)")
                else:
                    warn(f"{label}:{lineno} — `:latest` used; fine in compose.yaml for local dev, confirm intentional")

    k8s_dir = ROOT / "k8s"
    if k8s_dir.exists():
        for path in k8s_dir.rglob("*.yaml"):
            text = path.read_text()
            for lineno, line in enumerate(text.splitlines(), start=1):
                if re.search(r"image:\s*.*:latest", line):
                    fail(f"{path.relative_to(ROOT)}:{lineno} — `:latest` deployed via K8s manifest (§5.3 -8)")
                if re.search(r"REPLACE_WITH_SHA", line):
                    warn(f"{path.relative_to(ROOT)}:{lineno} — placeholder SHA tag still present; "
                         f"confirm your CD pipeline replaces this before applying (not a manual edit)")


def check_localhost_in_service_config() -> None:
    """Scan compose/k8s for literal 'localhost' used as a cross-service hostname."""
    for path in [ROOT / "compose.yaml", ROOT / "compose.prod.yaml"]:
        if not path.exists():
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "localhost" in line.lower() and "healthcheck" not in text.splitlines()[max(0, lineno - 3):lineno][0].lower():
                warn(f"{path.relative_to(ROOT)}:{lineno} — contains 'localhost'; confirm this isn't "
                     f"service-to-service (§5.3 -8). Healthcheck CMDs targeting their own container are fine.")


def check_published_db_cache_ports_in_prod() -> None:
    path = ROOT / "compose.prod.yaml"
    if not path.exists():
        return
    text = path.read_text()
    # crude YAML-ish scan: look for a `ports:` block under database/cache services
    for service in ("database", "cache"):
        m = re.search(rf"^\s*{service}:\s*\n(.*?)(?=^\s*\w+:\s*$|\Z)", text, re.M | re.S)
        if m and re.search(r"^\s*ports:\s*$", m.group(1), re.M):
            fail(f"compose.prod.yaml — `{service}` service has a `ports:` block; "
                 f"DB/cache must never be published in prod (§5.3 -8)")


def check_workflow_needs_gating() -> None:
    workflows_dir = ROOT / ".github" / "workflows"
    if not workflows_dir.exists():
        fail(".github/workflows/ is missing")
        return
    for path in workflows_dir.glob("*.yml"):
        text = path.read_text()
        # crude: any job containing docker/build-push-action with push:true (or a kubectl apply)
        # should also contain a `needs:` line somewhere in the file.
        publishes = "push: true" in text or "kubectl apply" in text
        if publishes and "needs:" not in text:
            fail(f"{path.relative_to(ROOT)} — appears to publish/deploy but has no `needs:` gating (§5.3 -8)")


def check_readme_and_docs_exist() -> None:
    required = [
        ROOT / "README.md",
        ROOT / "docs" / "ENGINEERING-NOTES.md",
        ROOT / "docs" / "RUNBOOK.md",
        ROOT / "docs" / "AI-USAGE.md",
        ROOT / "docs" / "adr" / "0001-provider-interface.md",
        ROOT / "docs" / "adr" / "0002-frontend-runtime-config.md",
        ROOT / "docs" / "adr" / "0003-deploy-by-sha.md",
        ROOT / "docs" / "adr" / "0004-pii-and-data-governance.md",
    ]
    for path in required:
        if not path.exists():
            fail(f"Missing required doc: {path.relative_to(ROOT)}")


def check_dockerignore_present() -> None:
    for d in ("backend", "frontend"):
        if not (ROOT / d / ".dockerignore").exists():
            fail(f"{d}/.dockerignore is missing (§3.1)")


def check_non_root_dockerfile() -> None:
    for d in ("backend", "frontend"):
        path = ROOT / d / "Dockerfile"
        if not path.exists():
            continue
        text = path.read_text()
        if "USER " not in text and d == "backend":
            fail(f"{d}/Dockerfile — no `USER` directive found; container likely runs as root (§3.1)")
        if d == "frontend" and "USER " not in text:
            warn(f"{d}/Dockerfile — no `USER` directive found; confirm your chosen "
                 f"non-root approach for the nginx stage (see the Dockerfile's own TODO)")


def main() -> int:
    check_no_env_committed()
    check_unpinned_images()
    check_localhost_in_service_config()
    check_published_db_cache_ports_in_prod()
    check_workflow_needs_gating()
    check_readme_and_docs_exist()
    check_dockerignore_present()
    check_non_root_dockerfile()

    # TODO(you): add checks for the items this script does NOT cover, e.g.:
    #   - scanning `git log -p` for accidentally-committed secrets (needs GitPython
    #     or shelling out to `git log -S`, deliberately not done here to keep this
    #     script dependency-free and safe to run repeatedly)
    #   - branch protection / PR review counts (needs the GitHub API + a token)
    #   - commit count and per-partner percentage (`git shortlog -sn`)
    #   - actual coverage percentage (parse pytest-cov output rather than re-deriving it here)

    print(f"\n{'=' * 60}")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  ✗ {f}")
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ! {w}")
    if not failures and not warnings:
        print("No issues found by this script's checks.")
    print(f"{'=' * 60}\n")
    print("Reminder: this is a lint, not a grader. A clean run here does not")
    print("guarantee a good mark — review §5.3 and the rubric yourself too.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
