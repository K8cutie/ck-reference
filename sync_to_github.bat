@echo off
setlocal

rem --- Paths ---
set "SRC=C:\ckchurch1"
set "DEST=G:\My Drive\Clearkeep\ck-reference"
set "REPO=G:\My Drive\Clearkeep\ck-reference"

rem --- Mirror sanitized files to Drive (no secrets / no heavy caches) ---
robocopy "%SRC%" "%DEST%" /E /R:1 /W:1 ^
 /XD .git .venv node_modules .pytest_cache __pycache__ dist build media ^
 /XF .env .env.* *.pem *.key *.sqlite *.bak *.log *.zip *.ics *.csv

rem --- Remove Windows desktop.ini clutter everywhere (including inside .git) ---
for /r "%REPO%" %%F in (desktop.ini) do del /f /q "%%F" >nul 2>&1
del /f /q "%REPO%\.git\refs\desktop.ini" 2>nul
del /f /q "%REPO%\.git\logs\refs\desktop.ini" 2>nul

rem --- Commit first, then rebase/pull, then push ---
cd /d "%REPO%"
git add -A
git commit -m "mirror" || echo No changes to commit.
git pull --rebase
git push origin main

endlocal
echo Done!
pause
