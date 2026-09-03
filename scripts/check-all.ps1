<#
.SYNOPSIS
    Runs every Phase 1 validation check for the Encrypted Chat Application.

.DESCRIPTION
    Convenience wrapper around the checks documented in README.md. Runs the
    backend suite (Ruff, mypy, pytest, pip-audit), the frontend suite (ESLint,
    tsc, Vitest, build, npm audit), and the repository-wide secret scan.

    This script is a convenience only — it is not a substitute for CI, and it
    does not change any check's behaviour. Every command below is the same one
    documented in README.md and run in CI.

.EXAMPLE
    .\scripts\check-all.ps1

.NOTES
    Run from the repository root. Requires the backend virtual environment to
    exist (server\.venv) and frontend dependencies to be installed (npm ci).
    Does not require Administrator.
#>

[CmdletBinding()]
param(
    # Skip the Gitleaks scan (useful if gitleaks is not on PATH).
    [switch]$SkipSecretScan
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()

function Invoke-Check {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][scriptblock]$Command
    )

    Write-Host ''
    Write-Host "--- $Name " -NoNewline -ForegroundColor Cyan
    Write-Host ('-' * [Math]::Max(0, 60 - $Name.Length)) -ForegroundColor Cyan

    Push-Location $WorkingDirectory
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            $script:failures.Add($Name)
            Write-Host "FAIL: $Name (exit $LASTEXITCODE)" -ForegroundColor Red
        }
        else {
            Write-Host "PASS: $Name" -ForegroundColor Green
        }
    }
    catch {
        $script:failures.Add($Name)
        Write-Host "FAIL: $Name — $_" -ForegroundColor Red
    }
    finally {
        Pop-Location
    }
}

$serverDir = Join-Path $repoRoot 'server'
$clientDir = Join-Path $repoRoot 'client'
$venvScripts = Join-Path $serverDir '.venv\Scripts'

if (-not (Test-Path $venvScripts)) {
    throw "Backend virtual environment not found at $venvScripts. See README.md > Setup."
}

# --- Backend --------------------------------------------------------------
Invoke-Check 'Ruff (lint)'        $serverDir { & "$venvScripts\ruff.exe" check . }
Invoke-Check 'Ruff (format)'      $serverDir { & "$venvScripts\ruff.exe" format --check . }
Invoke-Check 'mypy'               $serverDir { & "$venvScripts\mypy.exe" . }
Invoke-Check 'pytest'             $serverDir { & "$venvScripts\pytest.exe" }
Invoke-Check 'pip-audit'          $serverDir { & "$venvScripts\pip-audit.exe" -r requirements.txt }

# --- Frontend -------------------------------------------------------------
Invoke-Check 'ESLint'             $clientDir { npm run lint }
Invoke-Check 'TypeScript'         $clientDir { npm run typecheck }
Invoke-Check 'Vitest'             $clientDir { npm run test }
Invoke-Check 'Frontend build'     $clientDir { npm run build }
Invoke-Check 'npm audit'          $clientDir { npm audit --audit-level=high }

# --- Repository -----------------------------------------------------------
if (-not $SkipSecretScan) {
    if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
        Invoke-Check 'Gitleaks' $repoRoot { gitleaks dir . --config .gitleaks.toml }
    }
    else {
        Write-Host ''
        Write-Host 'SKIP: Gitleaks not found on PATH (winget install --id Gitleaks.Gitleaks -e)' -ForegroundColor Yellow
    }
}

# --- Summary --------------------------------------------------------------
Write-Host ''
Write-Host ('=' * 64)
if ($failures.Count -eq 0) {
    Write-Host 'All checks passed.' -ForegroundColor Green
    exit 0
}

Write-Host "$($failures.Count) check(s) failed:" -ForegroundColor Red
$failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
exit 1
