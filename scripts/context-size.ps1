<#
.SYNOPSIS
  Build-context size with and without .dockerignore, plus image sizes (rubric G / ENGINEERING-NOTES).
.EXAMPLE
  .\scripts\context-size.ps1
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Get-SizeKiB([string]$Path) {
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    [math]::Round(($sum | ForEach-Object { if ($_) { $_ } else { 0 } }) / 1KB)
}

function Get-ContextKiB([string]$Dir) {
    # Ask BuildKit what it really transfers: copy the whole context into a
    # throwaway scratch stage, export it, and measure the result.
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Set-Content -Path (Join-Path $tmp "Dockerfile") -Value "FROM scratch`nCOPY . /ctx" -Encoding ascii
        docker buildx build -q --no-cache -f (Join-Path $tmp "Dockerfile") --output "type=local,dest=$tmp/out" $Dir | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "docker buildx build failed for $Dir" }
        Get-SizeKiB (Join-Path $tmp "out/ctx")
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
}

"{0,-10} {1,15} {2,15}" -f "context", "without (KiB)", "with (KiB)"
foreach ($c in "backend", "frontend") {
    $dir = Join-Path $Root $c
    "{0,-10} {1,15} {2,15}" -f $c, (Get-SizeKiB $dir), (Get-ContextKiB $dir)
}
""
"Image sizes (after docker compose build):"
docker image ls --format "{{.Repository}}:{{.Tag}}  {{.Size}}" | Select-String -Pattern "^civicpulse-(backend|frontend)"
