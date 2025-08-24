<#  start-clearkeep.ps1  — one-click dev bootstrap for ClearKeep (Windows)
    - Starts/creates Postgres container (ckchurch) on port 5432
    - Ensures database ckchurch exists
    - Starts backend (Uvicorn) using venv Python
    - Starts frontend (Next.js dev)
#>

# ---------- SETTINGS ----------
$FrontendPath   = 'C:\ckchurch1\clearkeep-frontend-starter'
$BackendPath    = 'C:\ckchurch1\backend'
$VenvPython     = Join-Path $BackendPath '.venv\Scripts\python.exe'
$ApiModule      = 'app.main:app'
$ApiHost        = '127.0.0.1'
$ApiPort        = 8000

$DbContainer    = 'ckchurch'
$DbImage        = 'postgres:16'
$DbPort         = 5432
$DbName         = 'ckchurch'
$DbUser         = 'postgres'
$DbPassword     = 'postgres'

$EnsureRestartPolicy = $true

# ---------- HELPERS ----------
function Say([string]$msg) { Write-Host ('[CK] {0}' -f $msg) -ForegroundColor Cyan }
function Fail([string]$msg){ Write-Error ('[CK] {0}' -f $msg); exit 1 }

# ---------- 0) Pre-flight ----------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail 'Docker is not available. Please start Docker Desktop first.'
}

# ---------- 1) Ensure Postgres container ----------
$exists = $false
try {
  docker container inspect $DbContainer *> $null
  if ($LASTEXITCODE -eq 0) { $exists = $true }
} catch { $exists = $false }

if (-not $exists) {
  Say ("Creating Postgres container '{0}'..." -f $DbContainer)

  # Build args array to avoid backticks/quoting issues
  $dockerRun = @(
    'run','-d',
    '--name', $DbContainer,
    '-e', ('POSTGRES_PASSWORD={0}' -f $DbPassword),
    '-e', ('POSTGRES_DB={0}' -f $DbName),
    '-p', ('{0}:5432' -f $DbPort),
    $DbImage
  )
  & docker @dockerRun | Out-Null
  if ($LASTEXITCODE -ne 0) { Fail 'Failed to create Postgres container.' }
} else {
  Say ("Postgres container '{0}' exists." -f $DbContainer)
}

$inspect = @('inspect','-f','{{.State.Running}}', $DbContainer)
$state = (& docker @inspect).Trim()
if ($state -ne 'true') {
  Say 'Starting Postgres container...'
  & docker @('start', $DbContainer) | Out-Null
}

if ($EnsureRestartPolicy) {
  & docker @('update','--restart','unless-stopped', $DbContainer) *> $null
}

Say ("Waiting for Postgres on localhost:{0} ..." -f $DbPort)
$timeout = [DateTime]::UtcNow.AddSeconds(30)
$ok = $false
while ([DateTime]::UtcNow -lt $timeout) {
  $ok = Test-NetConnection -ComputerName 'localhost' -Port $DbPort -InformationLevel 'Quiet'
  if ($ok) { break }
  Start-Sleep -Milliseconds 400
}
if (-not $ok) { Fail ("Postgres did not open port {0} in time." -f $DbPort) }

Say ("Ensuring database '{0}' exists..." -f $DbName)
$existsSql = "SELECT 1 FROM pg_database WHERE datname='$DbName';"
$psqlCheck = @('exec', $DbContainer, 'psql', '-U', $DbUser, '-t', '-c', $existsSql)
$check = (& docker @psqlCheck 2>$null) -join ''
if (-not ($check.Trim() -match '1')) {
  & docker @('exec', $DbContainer, 'psql', '-U', $DbUser, '-c', ("CREATE DATABASE {0};" -f $DbName)) | Out-Null
  Say ("Created database {0}." -f $DbName)
} else {
  Say ("Database {0} already exists." -f $DbName)
}

# ---------- 2) Start backend ----------
if (Test-Path $VenvPython) {
  $py = $VenvPython
} else {
  $py = 'python'
  Say ("Warning: venv Python not found at {0} — falling back to 'python'." -f $VenvPython)
}
$apiArgs = @('-m','uvicorn', $ApiModule, '--host', $ApiHost, '--port', "$ApiPort", '--reload')

Say ("Launching backend (Uvicorn @{0}:{1})..." -f $ApiHost, $ApiPort)
Start-Process -WorkingDirectory $BackendPath -FilePath $py -ArgumentList $apiArgs -WindowStyle Normal -PassThru | Out-Null

# ---------- 3) Configure frontend ----------
$envLocalPath = Join-Path $FrontendPath '.env.local'
$desiredLine  = ('NEXT_PUBLIC_API_BASE=http://{0}:{1}' -f $ApiHost, $ApiPort)
if (-not (Test-Path $envLocalPath)) {
  Set-Content -Encoding Ascii -Path $envLocalPath -Value $desiredLine
  Say ("Created .env.local -> {0}" -f $desiredLine)
} else {
  $current = Get-Content $envLocalPath -Raw
  if ($current -notmatch 'NEXT_PUBLIC_API_BASE=') {
    Add-Content -Encoding Ascii -Path $envLocalPath -Value $desiredLine
    Say 'Appended NEXT_PUBLIC_API_BASE to .env.local'
  }
}

# ---------- 4) Start frontend ----------
Say 'Launching frontend (Next.js dev on :3000)...'
Start-Process -WorkingDirectory $FrontendPath -FilePath 'npm' -ArgumentList @('run','dev') -WindowStyle Normal -PassThru | Out-Null

# ---------- 5) Open browser ----------
Start-Process 'http://localhost:3000'
Say ("All set. Backend: http://{0}:{1}  |  Frontend: http://localhost:3000" -f $ApiHost, $ApiPort)

# ---------- 6) Pause ----------
Write-Host ''
Write-Host 'Press any key to close this window . . .' -ForegroundColor Yellow
[void][System.Console]::ReadKey($true)
