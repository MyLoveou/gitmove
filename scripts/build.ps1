#Requires -Version 5.1
param(
    [ValidateSet("all", "cli", "gui")]
    [string]$Target = "all",
    [switch]$Onedir
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    pip install -e ".[build]" -q
    $args = @("scripts/build.py", "--target", $Target)
    if ($Onedir) { $args += "--onedir" }
    python @args
}
finally {
    Pop-Location
}
