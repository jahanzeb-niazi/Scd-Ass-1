<#
.SYNOPSIS
  Record HPA state every 5 s while a load test runs, for the replicas-vs-load chart.
  Writes plain UTF-8/ASCII CSV (safe to feed to scripts/hpa_chart.py). Ctrl-C to stop.
.EXAMPLE
  .\scripts\record-hpa.ps1 -OutFile docs\evidence\hpa-samples.csv
#>
[CmdletBinding()]
param(
    [string]$OutFile = "docs/evidence/hpa-samples.csv",
    [int]$IntervalSeconds = 5
)
$dir = Split-Path -Parent $OutFile
if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
Set-Content -Path $OutFile -Value "epoch_s,current_replicas,desired_replicas,cpu_utilisation_pct" -Encoding ascii
Write-Host "recording to $OutFile every $IntervalSeconds s — Ctrl-C to stop"

$jsonpath = 'jsonpath={.status.currentReplicas},{.status.desiredReplicas},{.status.currentMetrics[0].resource.current.averageUtilization}'
while ($true) {
    $line = kubectl -n civicpulse get hpa backend-hpa -o $jsonpath 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $line) { $line = ",," }
    $row = "{0},{1}" -f [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(), $line
    Add-Content -Path $OutFile -Value $row -Encoding ascii
    Write-Host $row
    Start-Sleep -Seconds $IntervalSeconds
}
