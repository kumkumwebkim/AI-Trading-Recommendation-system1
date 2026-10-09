@echo off
REM ============================================
REM  Launch the Alerts service on port 8005
REM  (Uses the uvicorn web server package)
REM ============================================
cd /d D:\stock

set PY=D:\stock\venv\Scripts\python.exe

if not exist "%PY%" (
    echo [ERROR] Python not found at %PY%
    pause
    exit /b 1
)

echo Starting Alerts service on http://localhost:8005 ...
echo Press CTRL+C to stop.
echo.

"%PY%" -m uvicorn alerts.main:app --host 0.0.0.0 --port 8005

pause
