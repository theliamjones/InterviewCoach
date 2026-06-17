@echo off
title Interview Coach
cd /d "%~dp0"

if not exist .env (
    echo .env not found - copy .env.example to .env and add your ANTHROPIC_API_KEY.
    pause
    exit /b 1
)

echo Starting Interview Coach...
rem Open the browser once the server has had a moment to come up
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5050"

py app.py

pause
