#Requires -Version 5.1
param(
    [ValidateSet("all", "cli", "gui")]
    [string]$Target = "all",
    [switch]$Onedir,
    [switch]$Installer,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Push-Location $Root
try {
    pip install -e ".[build]" -q
    if ($Installer) {
        if ($Onedir) {
            Write-Warning "Installer packages onefile executables; -Onedir is ignored."
        }
        $installerArgs = @("scripts/build_installer.py")
        if ($Rebuild) { $installerArgs += "--rebuild" }
        python @installerArgs
        exit $LASTEXITCODE
    }
    $args = @("scripts/build.py", "--target", $Target)
    if ($Onedir) { $args += "--onedir" }
    python @args
}
finally {
    Pop-Location
}
