<#
.SYNOPSIS
  Install the Vertical Pod Autoscaler in recommender-only mode (CRD, RBAC, recommender).
  No updater, no admission controller: with updateMode "Off" nothing evicts pods. Idempotent.
.EXAMPLE
  .\scripts\install-vpa.ps1
  .\scripts\install-vpa.ps1 -CrdOnly
#>
[CmdletBinding()]
param(
    [string]$Version = "1.8.0",
    [switch]$CrdOnly
)
$ErrorActionPreference = "Stop"
$base = "https://raw.githubusercontent.com/kubernetes/autoscaler/vertical-pod-autoscaler-$Version/vertical-pod-autoscaler/deploy"

$files = @("vpa-v1-crd-gen.yaml")
if (-not $CrdOnly) { $files += "vpa-rbac.yaml", "recommender-deployment.yaml" }
foreach ($f in $files) {
    kubectl apply -f "$base/$f"
    if ($LASTEXITCODE -ne 0) { throw "kubectl apply failed for $f" }
}
if (-not $CrdOnly) {
    kubectl -n kube-system rollout status deploy/vpa-recommender --timeout=180s
    if ($LASTEXITCODE -ne 0) { throw "vpa-recommender did not become ready" }
}
