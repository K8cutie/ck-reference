@echo off
set "SRC=C:\ckchurch1"
set "DEST=G:\My Drive\ClearKeep\ck-reference"

rem Copy from project → sanitized share (no secrets / no data dumps)
robocopy "%SRC%" "%DEST%" /E /R:1 /W:1 ^
 /XD .git .venv node_modules .pytest_cache __pycache__ dist build media ^
 /XF .env .env.* *.pem *.key *.sqlite *.bak *.log *.zip *.ics *.csv

echo Done!
pause
