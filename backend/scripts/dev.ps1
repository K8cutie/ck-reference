# backend/scripts/dev.ps1
#Requires -Version 5.1
<#
Usage (dot-source to load functions into the current shell):
  Set-Location C:\ckchurch1\backend
  . .\scripts\dev.ps1

Then use:
  Use-DB ckchurch           # or: ckchurch_db
  Show-Context
  Start-Api                 # uvicorn app.main:app --reload
  Test-All                  # run all tests
  Test-File tests\test_sacrament_baptism.py
  Alembic-Upgrade           # upgrade head
  Alembic-Upgrade b1f3d2a4c5e6
#>

# --- Paths -------------------------------------------------------------------
$script:RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:VenvScript = Join-Path $script:RepoRoot '.venv\Scripts\Activate.ps1'

# --- Helpers -----------------------------------------------------------------
function Activate-Env {
  if (-not (Test-Path $script:VenvScript)) {
    Write-Warning "Virtual env not found at $script:VenvScript. Create it first:  python -m venv .venv"
    return
  }
  # Always (re)activate THIS repo's venv to avoid cross-repo bleed
  . $script:VenvScript | Out-Null
}

function Mask-Db([string]$url) {
  if (-not $url) { return '<unset>' }
  return ($url -replace '.*/([^/\?]+).*', '$1')
}

function Show-Context {
  $py = (Get-Command python -ErrorAction SilentlyContinue)
  $pySrc = if ($py) { $py.Source } else { '<python not found>' }
  $venv = if ($env:VIRTUAL_ENV) { $env:VIRTUAL_ENV } else { '<inactive>' }
  $pp   = if ($env:PYTHONPATH)  { $env:PYTHONPATH }  else { '<unset>' }

  Write-Host "Repo      :" $script:RepoRoot
  Write-Host "Python    :" $pySrc
  Write-Host "Pytest    :" "$pySrc -m pytest"
  Write-Host "VENV      :" $venv
  Write-Host "DATABASE  :" (Mask-Db $env:DATABASE_URL)
  Write-Host "PYTHONPATH:" $pp
}

function Use-DB {
  param(
    [ValidateSet('ckchurch','ckchurch_db')]
    [string]$Name = 'ckchurch'
  )
  switch ($Name) {
    'ckchurch'    { $env:DATABASE_URL = 'postgresql+psycopg2://postgres:postgres@localhost:5432/ckchurch' }
    'ckchurch_db' { $env:DATABASE_URL = 'postgresql+psycopg2://ckchurch_app:cksecret@localhost:5432/ckchurch_db' }
  }
  Write-Host "DATABASE_URL set ->" (Mask-Db $env:DATABASE_URL)
}

function Start-Api {
  if (-not $env:DATABASE_URL) { Use-DB 'ckchurch' | Out-Null }
  python -m uvicorn app.main:app --reload
}

function Test-All { python -m pytest -q }
function Test-File([Parameter(Mandatory=$true)][string]$Path) { python -m pytest -q $Path }

function Alembic-Upgrade {
  param([string]$Rev = 'head')
  python -m alembic upgrade $Rev
}

# --- bootstrap when sourcing -------------------------------------------------
Set-Location $script:RepoRoot
Activate-Env
$env:PYTHONPATH = $script:RepoRoot
if (-not $env:DATABASE_URL) { Use-DB 'ckchurch' | Out-Null }

Write-Host 'Dev helpers loaded. Try: Show-Context'
