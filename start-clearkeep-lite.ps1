<# start-clearkeep-lite.ps1  launches backend & frontend only (WinPS 5.1 compatible) #>

$FrontendPath = 'C:\ckchurch1\clearkeep-frontend-starter'
$BackendPath  = 'C:\ckchurch1\backend'
$PyVenv       = Join-Path $BackendPath '.venv\Scripts\python.exe'
$ApiHost      = '127.0.0.1'
$ApiPort      = 8000

function Say([string]$m){ Write-Host ("[CK] {0}" -f $m) -ForegroundColor Cyan }
function Fail([string]$m){ Write-Error ("[CK] {0}" -f $m); exit 1 }

# Pick Python (5.1-safe, no ternary)
$py = $PyVenv
if (-not (Test-Path $py)) {
  $py = 'python'
  Say ("Warning: venv python not found at {0}, using 'python' in PATH." -f $PyVenv)
}

# 1) Backend (Uvicorn)
$uvicornArgs = @('-m','uvicorn','app.main:app','--host',$ApiHost,'--port',"$ApiPort",'--reload')
Say ("Starting backend (Uvicorn @{0}:{1})..." -f $ApiHost,$ApiPort)
Start-Process -WorkingDirectory $BackendPath -FilePath $py -ArgumentList $uvicornArgs -WindowStyle Normal | Out-Null

# 2) Ensure frontend .env.local has API base (create or append if missing)
$envLocal = Join-Path $FrontendPath '.env.local'
$desired  = ('NEXT_PUBLIC_API_BASE=http://{0}:{1}' -f $ApiHost,$ApiPort)
if (-not (Test-Path $envLocal)) {
  Set-Content -Encoding Ascii -Path $envLocal -Value $desired
  Say ("Created .env.local -> {0}" -f $desired)
} else {
  $cur = Get-Content $envLocal -Raw
  if ($cur -notmatch 'NEXT_PUBLIC_API_BASE=') {
    Add-Content -Encoding Ascii -Path $envLocal -Value $desired
    Say 'Appended NEXT_PUBLIC_API_BASE to .env.local'
  }
}

# 3) Frontend (Next.js dev)
Say 'Starting frontend (Next.js dev on :3000)...'
Start-Process -WorkingDirectory $FrontendPath -FilePath 'cmd.exe' -ArgumentList @('/c','npm','run','dev') -WindowStyle Normal | Out-Null

# 4) Open browser
Start-Process 'http://localhost:3000'
Say ("All set. Backend: http://{0}:{1}  |  Frontend: http://localhost:3000" -f $ApiHost,$ApiPort)

# 5) Pause so you can see logs
Write-Host ''
Write-Host 'Press any key to close this window . . .' -ForegroundColor Yellow
[void][System.Console]::ReadKey($true)
