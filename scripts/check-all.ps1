<#
.SYNOPSIS
    Runs every Phase 1 validation check for the Encrypted Chat Application.

.DESCRIPTION
    Convenience wrapper around the checks documented in README.md. Runs the
    backend suite (Ruff, mypy, pytest, pip-audit), the frontend suite (ESLint,
    tsc, Vitest, build, npm audit), and the repository-wide secret scan.

    This script is a convenience only - it is not a substitute for CI, and it
    does not change any check's behaviour. Every command below is the same one
    documented in README.md and run in CI.

    Success is judged solely by process exit code. Several of these tools write
    normal output to stderr (pip-audit reports success there), so stderr is not
    treated as failure.

.EXAMPLE
    .\scripts\check-all.ps1

.NOTES
    Run from anywhere; paths are resolved relative to the repository root.
    Requires the backend virtual environment (server\.venv) and frontend
    dependencies (npm ci). Does not require Administrator.

    This file is intentionally pure ASCII: Windows PowerShell 5.1 reads .ps1
    files using the system ANSI codepage unless they carry a UTF-8 BOM, so
    non-ASCII characters here would corrupt the script's parsing.
#>

[CmdletBinding()]
param(
    # Skip the Gitleaks scan (useful if gitleaks is not on PATH).
    [switch]$SkipSecretScan
)

# Deliberately NOT using `Set-StrictMode -Version Latest`: it breaks npm's
# PowerShell shim. Deliberately NOT using `$ErrorActionPreference = 'Stop'`:
# it promotes benign native-command stderr output into terminating errors.
$ErrorActionPreference = 'Continue'

$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

function Invoke-Check {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$Exe,
        [string[]]$Arguments = @()
    )

    Write-Host ''
    $dashes = '-' * [Math]::Max(3, 58 - $Name.Length)
    Write-Host "--- $Name $dashes" -ForegroundColor Cyan

    Push-Location $WorkingDirectory
    try {
        & $Exe @Arguments
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($code -ne 0) {
        $failures.Add($Name) | Out-Null
        Write-Host "FAIL: $Name (exit $code)" -ForegroundColor Red
    }
    else {
        Write-Host "PASS: $Name" -ForegroundColor Green
    }
}

$serverDir   = Join-Path $repoRoot 'server'
$clientDir   = Join-Path $repoRoot 'client'
$venvScripts = Join-Path $serverDir '.venv\Scripts'

if (-not (Test-Path $venvScripts)) {
    Write-Host "Backend virtual environment not found at $venvScripts" -ForegroundColor Red
    Write-Host 'See README.md > Setup.' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $clientDir 'node_modules'))) {
    Write-Host 'Frontend dependencies not installed. Run `npm ci` in client/.' -ForegroundColor Red
    exit 1
}

# npm.cmd is invoked directly rather than `npm`, which resolves to a
# PowerShell shim that misbehaves under some execution settings.
$npm = 'npm.cmd'

# --- Backend --------------------------------------------------------------
Invoke-Check 'Ruff (lint)'    $serverDir "$venvScripts\ruff.exe"      @('check', '.')
Invoke-Check 'Ruff (format)'  $serverDir "$venvScripts\ruff.exe"      @('format', '--check', '.')
Invoke-Check 'mypy'           $serverDir "$venvScripts\mypy.exe"      @('.')
Invoke-Check 'pytest'         $serverDir "$venvScripts\pytest.exe"    @()
Invoke-Check 'pip-audit'      $serverDir "$venvScripts\pip-audit.exe" @('-r', 'requirements.txt')

# --- Frontend -------------------------------------------------------------
Invoke-Check 'ESLint'         $clientDir $npm @('run', 'lint')
Invoke-Check 'TypeScript'     $clientDir $npm @('run', 'typecheck')
Invoke-Check 'Vitest'         $clientDir $npm @('run', 'test')
Invoke-Check 'Frontend build' $clientDir $npm @('run', 'build')
Invoke-Check 'npm audit'      $clientDir $npm @('audit', '--audit-level=high')

# --- Repository -----------------------------------------------------------
if (-not $SkipSecretScan) {
    if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
        Invoke-Check 'Gitleaks' $repoRoot 'gitleaks' @('dir', '.', '--config', '.gitleaks.toml')
    }
    else {
        Write-Host ''
        Write-Host 'SKIP: gitleaks not on PATH (winget install --id Gitleaks.Gitleaks -e)' -ForegroundColor Yellow
    }
}

# --- Summary --------------------------------------------------------------
Write-Host ''
Write-Host ('=' * 64)
if ($failures.Count -eq 0) {
    Write-Host 'ALL CHECKS PASSED.' -ForegroundColor Green
    exit 0
}

Write-Host "$($failures.Count) check(s) FAILED:" -ForegroundColor Red
foreach ($f in $failures) { Write-Host "  - $f" -ForegroundColor Red }
exit 1
