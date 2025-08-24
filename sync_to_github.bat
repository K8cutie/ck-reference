@echo off
setlocal

rem --- Paths ---
set "SRC=C:\ckchurch1"
set "REPO=C:\ck-reference"

rem --- Sanitize + copy working files into the repo (no secrets / heavy caches) ---
robocopy "%SRC%" "%REPO%" /E /R:1 /W:1 ^
 /XD .git .venv node_modules .pytest_cache __pycache__ dist build media ^
 /XF .env .env.* *.pem *.key *.sqlite *.bak *.log *.zip *.ics *.csv

rem --- Remove Windows desktop.ini clutter (sometimes created by Explorer) ---
for /r "%REPO%" %%F in (desktop.ini) do del /f /q "%%F" >nul 2>&1

rem --- Commit & push to GitHub ---
cd /d "%REPO%"
git checkout main
git pull --rebase
git add -A
git commit -m "mirror (local -> repo)" || echo No changes to commit.
git push origin main

endlocal
echo Done!
pause
