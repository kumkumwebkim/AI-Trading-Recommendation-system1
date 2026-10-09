@echo off
REM ============================================
REM  Launch the ML Signal service on port 8000
REM ============================================
cd /d D:\stock

set PY=D:\stock\venv\Scripts\python.exe

if not exist "%PY%" (
    echo [ERROR] Python not found at %PY%
    pause
    exit /b 1
)

echo Starting ML Signal service on http://localhost:8000 ...
echo Docs: http://localhost:8000/docs
echo Press CTRL+C to stop.
echo.

"%PY%" -m uvicorn signals.api:app --host 0.0.0.0 --port 8000

pause
