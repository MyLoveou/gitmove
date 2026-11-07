# 在 gitmove sync pull 成功后，按装配单把规范库里的规则 / Agent / Skill
# 单向导出到本仓的 .cursor、.opencode、.dsh。内容不同的文件跳过，不加 -Force。
# 规范库成员还没检出时退出 0，避免一次拉取被刷新失败挡住。
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }

$root = (& git rev-parse --show-toplevel 2>$null | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($root)) {
    Write-Host 'refresh-runtime: 不在 git 仓库里，跳过' -ForegroundColor Yellow
    exit 0
}
$root = (Resolve-Path -LiteralPath $root).Path

$project = 'gitmove-v2'
$manifest = Join-Path $root 'workspace.toml'
if (Test-Path -LiteralPath $manifest) {
    $raw = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8
    $matched = [regex]::Match($raw, '(?m)^name\s*=\s*"([^"]+)"')
    if ($matched.Success -and -not [string]::IsNullOrWhiteSpace($matched.Groups[1].Value)) {
        $project = $matched.Groups[1].Value
    }
}

function Test-Spec([string]$Path) {
    return (Test-Path -LiteralPath (Join-Path $Path "projects/$project/assembly.json"))
}

$candidates = @()
if (-not [string]::IsNullOrWhiteSpace($env:GITMOVE_SPEC_ROOT)) { $candidates += $env:GITMOVE_SPEC_ROOT }
$candidates += (Join-Path $root 'spec')
$home = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
if ($home) { $candidates += (Join-Path $home '.gitmove\cache\spec') }

$spec = $null
foreach ($item in $candidates) {
    if ([string]::IsNullOrWhiteSpace($item)) { continue }
    if (Test-Spec $item) { $spec = (Resolve-Path -LiteralPath $item).Path; break }
}
if (-not $spec) {
    Write-Host "refresh-runtime: 找不到规范库成员 spec（没有 projects/$project/assembly.json），跳过" -ForegroundColor Yellow
    exit 0
}

$script = Join-Path $spec '.cursor\skills\project-assembly\scripts\assemble.ps1'
if (-not (Test-Path -LiteralPath $script)) {
    Write-Host "refresh-runtime: 规范库里没有 assemble.ps1，跳过" -ForegroundColor Yellow
    exit 0
}

& powershell -NoProfile -ExecutionPolicy Bypass -File $script -Project $project -Target $root -Root $spec
exit $LASTEXITCODE
