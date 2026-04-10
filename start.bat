@echo off
setlocal
title DreamAgent Orchestrator (Backend)

echo ========================================================
echo Starting DreamAgent Backend...
echo ========================================================
start "DreamAgent API" cmd /c "python -m uvicorn backend.main:app --port 8001 --reload"

echo ========================================================
echo Starting DreamAgent Frontend...
echo ========================================================
start "DreamAgent UI" cmd /c "cd "frontend of dreamAgent/DreamAgent-v10-UI" && npm run dev"

echo Done! Both services are spinning up in background windows.
pause
