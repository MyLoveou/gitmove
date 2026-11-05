# Publish gitmove-v2: push master + tags, then trigger the tag release via API.
#
# Usage:  pwsh scripts/publish.ps1 [-Tags v0.6.0,v0.5.0]
#
# Notes
# - Pushes use SSH (github.com:443 is blocked in some networks); the API uses the
#   stored git credential and must bypass the system proxy.
# - Tag pushes over SSH do not trigger workflows, so each tag is dispatched with
#   workflow_dispatch on its tag ref instead.
param(
    [string[]]$Tags = @("v0.6.0"),
    [string]$Remote = "ssh://git@github.com/MyLoveou/gitmove-v2.git",
    [string]$Repo = "MyLoveou/gitmove-v2"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "== push master =="
git push $Remote master

Write-Host "== push tags =="
git push $Remote @Tags

Write-Host "== dispatch releases =="
$payload = "protocol=https`nhost=github.com`n`n"
$filled = ($payload | git credential fill 2>$null) -split "`n"
$token = ($filled | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) { throw "no stored GitHub credential" }
$hdr = Join-Path $env:TEMP "gitmove-publish.hdr"
Set-Content -Path $hdr -Value ("Authorization: Bearer " + $token) -Encoding ascii -NoNewline
try {
    foreach ($tag in $Tags) {
        $body = Join-Path $env:TEMP "gitmove-dispatch.json"
        Set-Content -Path $body -Value ('{"ref":"' + $tag + '"}') -Encoding ascii
        $code = & curl.exe -sS --noproxy "*" --max-time 60 -X POST `
            -H "@$hdr" -H "Accept: application/vnd.github+json" -H "Content-Type: application/json" `
            --data-binary "@$body" -o NUL -w "%{http_code}" `
            "https://api.github.com/repos/$Repo/actions/workflows/release.yml/dispatches"
        Write-Host ("dispatch {0} -> HTTP {1}" -f $tag, $code)
        Start-Sleep -Seconds 2
    }
} finally {
    Remove-Item $hdr -ErrorAction SilentlyContinue
}
