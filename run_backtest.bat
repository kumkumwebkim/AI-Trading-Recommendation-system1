@echo off
cd /d D:\stock
echo ============================================
echo   Starting Backtest API on port 8002 ...
echo   Open:  http://localhost:8002/docs
echo   Stop:  press CTRL+C
echo ============================================
D:\stock\venv\Scripts\python.exe -m uvicorn backtesting.main:app --host 0.0.0.0 --port 8002 --reload
pause
