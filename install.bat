@echo off
REM install.bat — One-command DreamAgent setup for Windows

echo.
echo   ██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗
echo   ██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
echo   ██║  ██║██████╔╝█████╗  ███████║██╔████╔██║███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
echo   ██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
echo   ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
echo.
echo   Autonomous Multi-Model AI Agent Platform  v1.0.0
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Check/install pnpm

pnpm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing pnpm...
    npm install -g pnpm
)

REM Install Python package
echo [INFO] Installing DreamAgent Python package...
pip install -e . --quiet

REM Create .env if not exists
if not exist ".env" (
    copy .env.example .env >nul
    echo [WARN] Created .env from .env.example - add your API keys before using agents!
)

REM Install frontend
echo [INFO] Installing frontend dependencies...
dreamagent install-frontend

echo.
echo [OK] Installation complete!
echo.
echo   Start DreamAgent:
echo   ─────────────────
echo   dreamagent run
echo.
pause
