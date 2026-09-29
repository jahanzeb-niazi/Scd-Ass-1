<#
.SYNOPSIS
  One command to put CivicPulse on a local k3d cluster (dev overlay, seeded) — Windows / PowerShell.
.EXAMPLE
  .\scripts\k8s-up.ps1
  # then open http://civicpulse.localhost:8081
#>
[CmdletBinding()]
param(
    [string]$Cluster = "civicpulse",
    [int]$IngressPort = 8081
)
$ErrorActionPreference = "Stop"
$Ns = "civicpulse"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Native commands do not throw on failure in PowerShell: check exit codes explicitly.
# Deliberately a *simple* function (no param block): an advanced function would swallow
# flags like -p / -o as PowerShell common parameters (-PipelineVariable, -OutVariable).
function Invoke-Native {
    $Exe = $args[0]
    $ArgList = @($args | Select-Object -Skip 1)
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "failed ($LASTEXITCODE): $Exe $($ArgList -join ' ')" }
}

foreach ($bin in "docker", "k3d", "kubectl") {
    if (-not (Get-Command $bin -ErrorAction SilentlyContinue)) { throw "missing: $bin (install it and reopen the terminal)" }
}

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$dotenv = @{}
Get-Content .env | Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    $dotenv[$k.Trim()] = $v.Trim()
}
if (-not $dotenv["POSTGRES_PASSWORD"]) { throw "set POSTGRES_PASSWORD in .env" }

Write-Host "==> cluster" -ForegroundColor Cyan
# Do NOT redirect native stderr (*> / 2>) under $ErrorActionPreference="Stop": Windows
# PowerShell turns the first stderr line into a terminating error. `list -o json` exits 0
# with [] when nothing exists, so no stderr is involved at all.
$clusters = (& k3d cluster list -o json) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "k3d cluster list failed - is Docker Desktop running?" }
$exists = $false
if ($clusters.Trim()) {
    $exists = @($clusters | ConvertFrom-Json | Where-Object { $_.name -eq $Cluster }).Count -gt 0
}
if (-not $exists) {
    # k3d ships Traefik (ingress) and metrics-server (needed by the HPA).
    Invoke-Native k3d cluster create $Cluster --agents 1 -p "${IngressPort}:80@loadbalancer" --wait
}
# Rewrite kubeconfig for this cluster (fixes stale/invalid contexts) and switch to it.
Invoke-Native k3d kubeconfig merge $Cluster --kubeconfig-switch-context --kubeconfig-merge-default | Out-Null
Invoke-Native kubectl config use-context "k3d-$Cluster"
# Docker Desktop on Windows: k3d writes https://host.docker.internal:<port>, which often
# resolves to an unreachable address from the host. The API port is published on the
# host's loopback, so point kubectl at 127.0.0.1 (k3s's certificate covers it).
$server = kubectl config view -o "jsonpath={.clusters[?(@.name=='k3d-$Cluster')].cluster.server}"
if ($server -and $server -notmatch '://(127\.0\.0\.1|localhost|0\.0\.0\.0):') {
    $local = $server -replace '://[^:/]+:', '://127.0.0.1:'
    Write-Host "    kubeconfig server $server -> $local"
    Invoke-Native kubectl config set-cluster "k3d-$Cluster" "--server=$local" | Out-Null
}
Invoke-Native kubectl get nodes

Write-Host "==> images (built once, imported into the cluster nodes)" -ForegroundColor Cyan
Invoke-Native docker build -t civicpulse-backend:dev backend
Invoke-Native docker build -t civicpulse-frontend:dev frontend
Invoke-Native k3d image import civicpulse-backend:dev civicpulse-frontend:dev -c $Cluster

# Third-party images: pull once on the host (uses Docker Desktop's registry mirror) and
# import, so the cluster nodes never need to reach Docker Hub / registry.k8s.io themselves.
$thirdParty = "postgres:16-alpine", "redis:7-alpine", "registry.k8s.io/autoscaling/vpa-recommender:1.8.0"
# Docker Desktop's containerd image store keeps multi-arch indexes whose other platforms are
# missing locally; `k3d image import <name>` then fails with "content digest ... not found".
# Saving a single platform to a tarball and importing the tarball avoids that.
$platform = "linux/" + (& docker version -f "{{.Server.Arch}}")
foreach ($img in $thirdParty) { Invoke-Native docker pull --platform $platform $img }
$tar = Join-Path ([IO.Path]::GetTempPath()) "civicpulse-thirdparty.tar"
Invoke-Native docker save --platform $platform -o $tar @thirdParty
Invoke-Native k3d image import $tar -c $Cluster
Remove-Item $tar -ErrorAction SilentlyContinue

Write-Host "==> VPA (recommender only)" -ForegroundColor Cyan
try {
    & (Join-Path $PSScriptRoot "install-vpa.ps1")
} catch {
    # VPA only produces recommendations (updateMode Off): the app does not depend on it.
    Write-Warning "VPA recommender not ready yet ($_). Continuing; check later with: kubectl -n kube-system get pods -l app=vpa-recommender"
}

Write-Host "==> namespace + secret (from .env, never from a committed file)" -ForegroundColor Cyan
Invoke-Native kubectl apply -f k8s/base/namespace.yaml
$secretYaml = kubectl -n $Ns create secret generic civicpulse-secrets `
    "--from-literal=POSTGRES_PASSWORD=$($dotenv['POSTGRES_PASSWORD'])" `
    "--from-literal=GEMINI_API_KEY=$($dotenv['GEMINI_API_KEY'])" `
    --dry-run=client -o yaml
if ($LASTEXITCODE -ne 0) { throw "could not render the secret" }
$secretYaml | kubectl apply -f -
if ($LASTEXITCODE -ne 0) { throw "could not apply the secret" }

Write-Host "==> apply dev overlay" -ForegroundColor Cyan
$existed = kubectl -n $Ns get deploy backend --ignore-not-found -o name
Invoke-Native kubectl -n $Ns delete job migrate --ignore-not-found   # Jobs are immutable
Invoke-Native kubectl apply -k k8s/overlays/dev
Invoke-Native kubectl -n $Ns wait --for=condition=complete job/migrate --timeout=300s
if ($existed) {
    # Same :dev tag, new image content: force the pods to pick it up.
    Invoke-Native kubectl -n $Ns rollout restart deploy/backend deploy/frontend
}
Invoke-Native kubectl -n $Ns rollout status deploy/backend --timeout=300s
Invoke-Native kubectl -n $Ns rollout status deploy/frontend --timeout=300s

kubectl -n $Ns get pods,svc,ingress,hpa
Write-Host ""
Write-Host "CivicPulse is up:  http://civicpulse.localhost:$IngressPort" -ForegroundColor Green