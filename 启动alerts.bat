@echo off
cd /d D:\stock
echo ============================================
echo   Starting Alerts API on port 8005 ...
echo   Open:  http://localhost:8005/docs
echo   Stop:  press CTRL+C
echo ============================================
D:\stock\venv\Scripts\python.exe -m uvicorn alerts.main:app --host 0.0.0.0 --port 8005
pause
