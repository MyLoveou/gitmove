#Requires -Version 5.1
<#
.SYNOPSIS
  Build gitmove Windows setup.exe (PyInstaller + Inno Setup).

.EXAMPLE
  .\scripts\build-installer.ps1
  .\scripts\build-installer.ps1 -Rebuild
#>
param(
    [string]$Version = "",
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    pip install -e ".[build]" -q
    $args = @("scripts/build_installer.py")
    if ($Version) { $args += @("--version", $Version) }
    if ($Rebuild) { $args += "--rebuild" }
    python @args
}
finally {
    Pop-Location
}
