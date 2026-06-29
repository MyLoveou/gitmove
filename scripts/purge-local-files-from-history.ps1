#Requires -Version 5.1
<#
.SYNOPSIS
  Remove accidentally committed local config files from entire git history.

.WARNING
  Rewrites history. Coordinate with teammates before force-pushing.
#>
param(
    [string[]]$Files = @("config.local.json", "*.local.json")
)

$filterRepo = Get-Command git-filter-repo -ErrorAction SilentlyContinue
if (-not $filterRepo) {
    Write-Error "Install git-filter-repo first: pip install git-filter-repo"
    exit 1
}

Write-Host "This will rewrite history to remove:" ($Files -join ", ")
$ans = Read-Host "Continue? [y/N]"
if ($ans -notin @("y", "Y")) {
    Write-Host "Aborted."
    exit 0
}

foreach ($file in $Files) {
    git filter-repo --path $file --invert-paths --force
}

Write-Host "Done. Verify with: git log --all -- config.local.json"
Write-Host "Then force-push only if your team agrees: git push --force-with-lease"
