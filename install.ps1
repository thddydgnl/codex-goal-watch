[CmdletBinding()]
param(
    [switch]$Uninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PluginName = "codex-one-turn"
$MarketplaceName = "codex-one-turn"
$RemoteSource = "thddydgnl/codex-goal-watch"
$MinimumCodexVersion = [version]"0.133.0"
$MinimumPythonVersion = [version]"3.10.0"
$CodexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }

function Write-Step([string]$Message) {
    Write-Host $Message
}

function Assert-LastExitCode([string]$Action) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed with exit code $LASTEXITCODE"
    }
}

function Get-NumericVersion([string]$Value) {
    $match = [regex]::Match($Value, "\d+\.\d+\.\d+")
    if (-not $match.Success) {
        throw "Could not parse version from: $Value"
    }
    return [version]$match.Value
}

function Remove-LegacyAgentsBlock([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    $content = [System.IO.File]::ReadAllText($Path)
    if (-not $content.Contains("<!-- goal-watch:start -->")) {
        return
    }
    $pattern = "(?ms)^<!-- goal-watch:start -->.*?^<!-- goal-watch:end -->\r?\n?"
    $updated = [regex]::Replace($content, $pattern, "")
    [System.IO.File]::WriteAllText(
        $Path,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Step "Removed legacy goal-watch block from $Path"
}

function Remove-LegacyGoalWatch {
    $legacy = Join-Path $CodexDir "skills\goal-watch"
    if (Test-Path -LiteralPath $legacy) {
        Remove-Item -LiteralPath $legacy -Recurse -Force
        Write-Step "Removed legacy goal-watch skill from $legacy"
    }
    Remove-LegacyAgentsBlock (Join-Path $CodexDir "AGENTS.md")
    Remove-LegacyAgentsBlock (Join-Path $CodexDir "AGENTS.override.md")
}

function Remove-OneTurn {
    if (Get-Command codex -ErrorAction SilentlyContinue) {
        & codex plugin remove "$PluginName@$MarketplaceName" *> $null
        & codex plugin marketplace remove $MarketplaceName *> $null
    }
    Remove-LegacyGoalWatch
    Write-Step "Codex OneTurn has been uninstalled. Job logs were preserved."
}

if ($Uninstall) {
    Remove-OneTurn
    exit 0
}

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI is required"
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.10 or newer must be available as the 'python' command"
}

$codexVersion = Get-NumericVersion ((& codex --version) | Out-String)
Assert-LastExitCode "Reading the Codex version"
if ($codexVersion -lt $MinimumCodexVersion) {
    throw "Codex $MinimumCodexVersion or newer is required (found $codexVersion)"
}

$pythonVersion = Get-NumericVersion ((& python --version) | Out-String)
Assert-LastExitCode "Reading the Python version"
if ($pythonVersion -lt $MinimumPythonVersion) {
    throw "Python $MinimumPythonVersion or newer is required (found $pythonVersion)"
}

Remove-LegacyGoalWatch

$localMarketplace = Join-Path $PSScriptRoot ".agents\plugins\marketplace.json"
if (Test-Path -LiteralPath $localMarketplace -PathType Leaf) {
    $source = $PSScriptRoot
    $sourceKind = "local"
} else {
    $source = $RemoteSource
    $sourceKind = "git"
}

$marketplaceOutput = (& codex plugin marketplace list --json) | Out-String
Assert-LastExitCode "Listing Codex plugin marketplaces"
$marketplaceList = $marketplaceOutput | ConvertFrom-Json
$marketplaceExists = @(
    $marketplaceList.marketplaces | Where-Object { $_.name -eq $MarketplaceName }
).Count -gt 0

if ($marketplaceExists) {
    if ($sourceKind -eq "git") {
        & codex plugin marketplace upgrade $MarketplaceName | Out-Null
        Assert-LastExitCode "Updating the OneTurn marketplace"
        Write-Step "Updated marketplace: $MarketplaceName"
    } else {
        Write-Step "Using local marketplace: $MarketplaceName"
    }
} else {
    & codex plugin marketplace add $source | Out-Null
    Assert-LastExitCode "Adding the OneTurn marketplace"
    Write-Step "Added marketplace: $MarketplaceName"
}

& codex plugin add "$PluginName@$MarketplaceName" | Out-Null
Assert-LastExitCode "Installing Codex OneTurn"
Write-Step "Installed plugin: $PluginName"
Write-Host ""
Write-Step "Next steps:"
Write-Step "  1. Restart Codex and start a new task."
Write-Step "  2. In Codex CLI, open /hooks and trust the two OneTurn hooks."
Write-Step "  3. Ask normally, or write: OneTurn으로 이 작업을 실행해줘."
Write-Host ""
Write-Step "Uninstall: powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall"
