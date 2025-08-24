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

rem --- Commit & push to GitHub ---
cd /d "%REPO%"
git pull --rebase
git add -A
git commit -m "mirror" || echo No changes to commit.
git push origin main

endlocal
echo Done!
pause
