#!/usr/bin/env python3
"""Pre-submission lint for CivicPulse — catches the mechanical failures behind §5.3.

    python scripts/check_submission.py

It is a lint, not a grader: a clean run does not guarantee a good mark; a dirty
run nearly guarantees a bad one. Exit code 1 if any FAIL. Needs PyYAML
(`pip install pyyaml`). If the course provides its own check_submission.py,
run that one too — it is authoritative.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
results: list[tuple[str, str, str]] = []  # (status, check, detail)


def ok(check: str, detail: str = "") -> None:
    results.append(("PASS", check, detail))


def fail(check: str, detail: str) -> None:
    results.append(("FAIL", check, detail))


def warn(check: str, detail: str) -> None:
    results.append(("WARN", check, detail))


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def load_yaml_docs(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [d for d in yaml.safe_load_all(f) if isinstance(d, dict)]


# --------------------------------------------------------------- layout (§5.7)
REQUIRED = [
    "backend/app/routes",
    "backend/app/services",
    "backend/app/repositories",
    "backend/app/providers",
    *[
        f"backend/app/providers/triage/{m}.py"
        for m in ("base", "llm", "ollama", "rules", "simulated", "factory")
    ],
    "backend/alembic/versions",
    "backend/tests",
    "backend/Dockerfile",
    "backend/.dockerignore",
    "backend/pyproject.toml",
    "frontend/src/components",
    "frontend/src/pages",
    "frontend/src/api",
    "frontend/tests",
    "frontend/Dockerfile",
    "frontend/.dockerignore",
    "frontend/nginx.conf",
    "frontend/package.json",
    *[
        f"k8s/base/{m}.yaml"
        for m in (
            "namespace",
            "backend",
            "frontend",
            "postgres",
            "redis",
            "ingress",
            "configmap",
            "secret",
            "hpa",
            "vpa",
            "pdb",
            "kustomization",
        )
    ],
    "k8s/overlays/dev/kustomization.yaml",
    "k8s/overlays/prod/kustomization.yaml",
    "load/k6-script.js",
    "docs/ENGINEERING-NOTES.md",
    "docs/RUNBOOK.md",
    "docs/AI-USAGE.md",
    "docs/TRIAGE.md",
    "docs/evidence",
    ".github/workflows/ci.yml",
    ".github/workflows/cd.yml",
    ".github/workflows/release.yml",
    "compose.yaml",
    "compose.prod.yaml",
    ".env.example",
    ".gitignore",
    "README.md",
    "LICENSE",
]


def check_layout() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        fail("repository layout (§5.7)", "missing: " + ", ".join(missing))
    else:
        ok("repository layout (§5.7)")
    adrs = sorted((ROOT / "docs/adr").glob("000[1-4]-*.md"))
    if len(adrs) == 4:
        ok("four ADRs present")
    else:
        fail("four ADRs present", f"found {len(adrs)} in docs/adr")


# ---------------------------------------------- secrets in git history (−20)
SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "Google API key"),
    (re.compile(r"gsk_[0-9A-Za-z]{20,}"), "Groq API key"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "OpenAI-style key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]


def check_secrets() -> None:
    tracked = git("ls-files").splitlines()
    envs = [
        f for f in tracked if re.search(r"(^|/)\.env($|\.)", f) and not f.endswith(".env.example")
    ]
    if envs:
        fail("no .env committed (−20)", "tracked: " + ", ".join(envs))
    else:
        ok("no .env committed (−20)")

    history = git("log", "--all", "-p", "--no-color")
    if not history:
        warn("secrets in git history (−20)", "no git history found — run inside the repository")
        return
    hits = {label for pat, label in SECRET_PATTERNS if pat.search(history)}
    ever_env = git("log", "--all", "--diff-filter=A", "--name-only", "--pretty=format:")
    env_files = {f for f in ever_env.splitlines() if re.search(r"(^|/)\.env$", f)}
    if hits or env_files:
        fail(
            "secrets in git history (−20)",
            f"found {sorted(hits)} {sorted(env_files)} — rotate the credential, "
            "rewrite history, write an incident note",
        )
    else:
        ok("secrets in git history (−20)")

    secret = (
        (ROOT / "k8s/base/secret.yaml").read_text(encoding="utf-8")
        if (ROOT / "k8s/base/secret.yaml").exists()
        else ""
    )
    values = re.findall(r"^\s+[A-Z_]+:\s*(\S+)\s*$", secret, re.M)
    bad = [v for v in values if v not in ("REPLACE_ME", '""', "''")]
    if bad:
        fail("k8s Secret has placeholders only (−15)", f"non-placeholder values: {len(bad)}")
    else:
        ok("k8s Secret has placeholders only (−15)")


# -------------------------------------------------- pinned images (−8)
def image_pinned(ref: str) -> bool:
    if "@sha256:" in ref:
        return True
    if "${" in ref:
        return True  # interpolated tag (IMAGE_TAG) — checked separately
    name, _, tag = ref.rpartition(":")
    if not name or "/" in tag:
        return False
    return tag not in ("", "latest")


def check_pinned_images() -> None:
    problems = []
    for df in ("backend/Dockerfile", "frontend/Dockerfile"):
        text = (ROOT / df).read_text(encoding="utf-8")
        args = dict(re.findall(r"^ARG\s+(\w+)=(\S+)", text, re.M))
        for ref in re.findall(r"^FROM\s+(\S+)", text, re.M):
            ref = re.sub(r"\$\{(\w+)\}", lambda m: args.get(m.group(1), m.group(0)), ref)
            if ref in ("builder", "build", "runtime") or ref.startswith("${"):
                continue
            if not image_pinned(ref):
                problems.append(f"{df}: {ref}")
    for cf in ("compose.yaml", "compose.prod.yaml"):
        for name, svc in (load_yaml_docs(ROOT / cf)[0].get("services") or {}).items():
            img = svc.get("image")
            if img and not img.startswith("civicpulse-") and not image_pinned(img):
                problems.append(f"{cf}: {name} → {img}")
    for f in (ROOT / "k8s/base").glob("*.yaml"):
        for m in re.finditer(r"^\s+image:\s*(\S+)", f.read_text(encoding="utf-8"), re.M):
            ref = m.group(1)
            if not ref.startswith("civicpulse-") and not image_pinned(ref):
                problems.append(f"{f.relative_to(ROOT)}: {ref}")
    if problems:
        fail("every image pinned to a tag (−8)", "; ".join(problems))
    else:
        ok("every image pinned to a tag (−8)")


# ------------------------------------------- localhost service-to-service (−8)
def check_localhost() -> None:
    scan = [
        ROOT / "compose.yaml",
        ROOT / "compose.prod.yaml",
        ROOT / "frontend/nginx.conf",
        *(ROOT / "k8s").rglob("*.yaml"),
        *(ROOT / "backend/app").rglob("*.py"),
        *(ROOT / "frontend/src").rglob("*.ts*"),
    ]
    hits = []
    for f in scan:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("#", "//", "*")):
                continue  # comments are not service-to-service traffic
            if (
                re.search(r"\blocalhost\b|127\.0\.0\.1", line)
                and "healthz" not in line
                and "/health" not in line
                and "/-/ready" not in line
                and "api/health" not in line
                and "civicpulse.localhost" not in line
            ):
                hits.append(f"{f.relative_to(ROOT)}:{n}")
    if hits:
        fail("no localhost for service-to-service (−8)", ", ".join(hits))
    else:
        ok(
            "no localhost for service-to-service (−8)",
            "healthchecks against the container itself are fine",
        )


# ------------------------------------------------- network segmentation (−8)
def check_networks() -> None:
    for cf in ("compose.yaml", "compose.prod.yaml"):
        doc = load_yaml_docs(ROOT / cf)[0]
        nets = doc.get("networks") or {}
        svcs = doc.get("services") or {}
        problems = []
        if (nets.get("internal") or {}).get("internal") is not True:
            problems.append("network `internal` lacks internal: true")
        if sorted(svcs.get("frontend", {}).get("networks", [])) != ["edge"]:
            problems.append("frontend must be on edge only")
        for s in ("database", "cache"):
            if sorted(svcs.get(s, {}).get("networks", [])) != ["internal"]:
                problems.append(f"{s} must be on internal only")
        if sorted(svcs.get("backend", {}).get("networks", [])) != ["edge", "internal"]:
            problems.append("backend must bridge edge and internal")
        if problems:
            fail(f"{cf}: frontend cannot reach database (−8)", "; ".join(problems))
        else:
            ok(f"{cf}: frontend cannot reach database (−8)")


# ---------------------------------------------------------- compose rules
def check_compose() -> None:
    prod = load_yaml_docs(ROOT / "compose.prod.yaml")[0]
    svcs = prod.get("services") or {}
    problems = []
    raw = (ROOT / "compose.prod.yaml").read_text(encoding="utf-8")
    if re.search(r"^\s+build:", raw, re.M):
        problems.append("build: key present")
    for s in ("database", "cache"):
        if svcs.get(s, {}).get("ports"):
            problems.append(f"{s} publishes a port (−8)")
    for s in ("backend", "frontend"):
        if "${IMAGE_TAG" not in raw.split(f"\n  {s}:")[0] and "${IMAGE_TAG" not in raw:
            problems.append(f"{s} image not tagged with ${{IMAGE_TAG}}")
    if ":latest" in raw:
        problems.append(":latest in production compose (−8)")
    if problems:
        fail("compose.prod.yaml rules", "; ".join(problems))
    else:
        ok("compose.prod.yaml rules", "image: only, ${IMAGE_TAG}, no DB/cache ports")

    dev = load_yaml_docs(ROOT / "compose.yaml")[0]
    no_hc = [
        n for n, s in dev["services"].items() if "healthcheck" not in s and s.get("restart") != "no"
    ]
    if no_hc:
        fail(
            "compose healthchecks", "long-running services without healthcheck: " + ", ".join(no_hc)
        )
    else:
        ok("compose healthchecks", 'one-shot jobs (restart: "no") excepted')
    vols = set((dev.get("volumes") or {}).keys())
    if {"pgdata", "redisdata", "ollama_models"} <= vols:
        ok("three named volumes")
    else:
        fail("three named volumes", f"found {sorted(vols)}")
    if (ROOT / ".env.example").exists() and ".env" in (ROOT / ".gitignore").read_text(
        encoding="utf-8"
    ):
        ok(".env.example committed, .env gitignored")
    else:
        fail(".env.example committed, .env gitignored", "check .gitignore / .env.example")


# ------------------------------------------------------------- kubernetes
def check_k8s() -> None:
    docs = []
    for f in (ROOT / "k8s/base").glob("*.yaml"):
        if f.name != "kustomization.yaml":
            docs.extend(load_yaml_docs(f))
    kinds = {(d.get("kind"), d.get("metadata", {}).get("name")) for d in docs}
    if ("StatefulSet", "postgres") in kinds and ("Deployment", "postgres") not in kinds:
        sts = next(d for d in docs if d.get("kind") == "StatefulSet")
        if sts["spec"].get("volumeClaimTemplates"):
            ok("PostgreSQL is a StatefulSet with a PVC (−8)")
        else:
            fail("PostgreSQL is a StatefulSet with a PVC (−8)", "no volumeClaimTemplates")
    else:
        fail("PostgreSQL is a StatefulSet with a PVC (−8)", "postgres is not a StatefulSet")

    bad_svc = [
        d["metadata"]["name"]
        for d in docs
        if d.get("kind") == "Service" and d["spec"].get("type", "ClusterIP") != "ClusterIP"
    ]
    if bad_svc:
        fail("all Services ClusterIP (−8 for DB)", ", ".join(bad_svc))
    else:
        ok("all Services ClusterIP (−8 for DB)")

    missing_res = []
    for d in docs:
        if d.get("kind") in ("Deployment", "StatefulSet", "Job"):
            for c in d["spec"]["template"]["spec"]["containers"]:
                r = c.get("resources", {})
                if not r.get("requests", {}).get("cpu") or not r.get("limits"):
                    missing_res.append(f"{d['metadata']['name']}/{c['name']}")
    if missing_res:
        fail("requests + limits on every container", ", ".join(missing_res))
    else:
        ok("requests + limits on every container")

    backend = next(
        d for d in docs if d.get("kind") == "Deployment" and d["metadata"]["name"] == "backend"
    )
    c = backend["spec"]["template"]["spec"]["containers"][0]
    probes_ok = (
        c.get("livenessProbe", {}).get("httpGet", {}).get("path") == "/health"
        and c.get("readinessProbe", {}).get("httpGet", {}).get("path") == "/ready"
        and "startupProbe" in c
    )
    (ok if probes_ok else fail)(
        "probes: liveness /health, readiness /ready, startup",
        "" if probes_ok else "check backend.yaml",
    )

    vpa = next((d for d in docs if d.get("kind") == "VerticalPodAutoscaler"), None)
    if vpa and vpa["spec"].get("updatePolicy", {}).get("updateMode") == "Off":
        ok("VPA in recommender mode (Off)")
    else:
        fail("VPA in recommender mode (Off)", 'updateMode must be "Off"')

    ns_ok = "namespace: civicpulse" in (ROOT / "k8s/base/kustomization.yaml").read_text(
        encoding="utf-8"
    )
    (ok if ns_ok else fail)(
        "everything in namespace civicpulse", "" if ns_ok else "set namespace in kustomization"
    )


# ----------------------------------------------------------------- CI/CD
PUBLISH = re.compile(r"push:\s*true|docker push|kubectl apply|cosign sign|action-gh-release")


def check_workflows() -> None:
    for wf in ("ci.yml", "cd.yml", "release.yml"):
        path = ROOT / ".github/workflows" / wf
        data = load_yaml_docs(path)[0]
        if "permissions" not in data:
            fail(f"{wf}: top-level permissions block", "missing")
        else:
            ok(f"{wf}: top-level permissions block")
        raw = path.read_text(encoding="utf-8")
        for m in re.finditer(r"uses:\s*([\w\-./]+)@(\S+)", raw):
            if m.group(1).startswith("./"):
                continue
            if m.group(2) in ("main", "master", "latest"):
                fail(f"{wf}: actions pinned", f"{m.group(1)}@{m.group(2)}")
        for name, job in (data.get("jobs") or {}).items():
            body = yaml.safe_dump(job)
            if PUBLISH.search(body) and "needs" not in job:
                fail(f"{wf}: publishing job gated by needs: (−8)", f"job `{name}` has no needs:")
        if re.search(r"(kubectl (set image|apply)|image:).*:latest", raw):
            fail(f"{wf}: never deploys :latest (−8)", "a deploy step references :latest")
    if not any(r[0] == "FAIL" and "needs" in r[1] for r in results):
        ok("publishing/deploying jobs gated by needs: (−8)")


# ---------------------------------------------------------- git hygiene
def check_git() -> None:
    log = git("log", "--pretty=%s")
    if not log:
        warn("git history", "not a git repository yet")
        return
    subjects = log.splitlines()
    conv = [
        s
        for s in subjects
        if re.match(
            r"^(feat|fix|docs|chore|refactor|test|ci|build|perf|style|revert)(\(.+\))?!?: ", s
        )
    ]
    n = len(subjects)
    (ok if n >= 35 else warn)("≥ 35 commits", f"{n} commits")
    ratio = len(conv) / n if n else 0
    (ok if ratio >= 0.9 else warn)("conventional commit prefixes", f"{ratio:.0%} of subjects")
    shortlog = git("shortlog", "-sn", "--all", "--no-merges")
    counts = [int(line.split()[0]) for line in shortlog.splitlines() if line.strip()]
    if len(counts) >= 2:
        share = min(counts[:2]) / sum(counts[:2])
        (ok if share >= 0.35 else warn)("neither partner below 35%", f"lowest share {share:.0%}")
    else:
        warn("neither partner below 35%", "only one author so far")
    merges_on_main = git("log", "main", "--first-parent", "--no-merges", "--pretty=%h %s")
    if merges_on_main.strip():
        warn(
            "no direct commits to main (−5)",
            "non-merge commits on main's first-parent line: "
            + str(len(merges_on_main.splitlines()))
            + " (fine only for the initial commit)",
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles
    for fn in (
        check_layout,
        check_secrets,
        check_pinned_images,
        check_localhost,
        check_networks,
        check_compose,
        check_k8s,
        check_workflows,
        check_git,
    ):
        try:
            fn()
        except Exception as exc:  # a crashed check is itself a finding
            fail(fn.__name__, f"check crashed: {type(exc).__name__}: {exc}")
    width = max(len(c) for _, c, _ in results)
    for status, check, detail in results:
        mark = {"PASS": "✔", "WARN": "!", "FAIL": "✘"}[status]
        print(f"{mark} {status:4}  {check:<{width}}  {detail}")
    fails = sum(1 for r in results if r[0] == "FAIL")
    warns = sum(1 for r in results if r[0] == "WARN")
    print(f"\n{len(results)} checks · {fails} FAIL · {warns} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
