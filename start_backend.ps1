# C:\ckchurch1\start_backend.ps1
$ErrorActionPreference = 'Stop'

$root = 'C:\ckchurch1\backend'
Set-Location $root

# Ensure venv exists
if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  py -3 -m venv .\.venv
}

# Activate venv
. .\.venv\Scripts\Activate.ps1

# Ensure deps present (first run or fresh machine)
if (-not (Get-Command uvicorn -ErrorAction SilentlyContinue)) {
  pip install --upgrade pip
  pip install -r .\requirements.txt
}

# Nuke any process-level override for safety
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

# Always load this .env (forces psycopg2 URL in your file)
$envfile = Join-Path $root '.env'
uvicorn app.main:app --reload --env-file $envfile
