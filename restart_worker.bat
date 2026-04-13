@echo off
title DreamAgent Worker Restart
echo ========================================================
echo  Restarting DreamAgent Distributed Worker...
echo ========================================================

:: Kill the old worker process if running
echo [1/3] Stopping old worker...
taskkill /FI "WINDOWTITLE eq DreamAgent Worker*" /F >nul 2>&1
timeout /t 2 /nobreak >nul

:: Also kill by script name as fallback
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /C:"PID:"') do (
    wmic process where "ProcessId=%%i" get CommandLine 2>nul | findstr /C:"worker.py" >nul && (
        echo Found worker PID %%i, terminating...
        taskkill /PID %%i /F >nul 2>&1
    )
)
timeout /t 1 /nobreak >nul

:: Start fresh worker
echo [2/3] Starting new worker...
start "DreamAgent Worker" cmd /c "python backend\worker.py"

echo [3/3] Worker restarted! New timeouts are now active:
echo   - Per-step timeout:   90s  (was 30s)
echo   - Pipeline timeout:  300s  (was 45s)  
echo   - Task outer limit:  600s  (was 60s)
echo.
echo Press any key to close this window...
pause >nul
