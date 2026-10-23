@echo off
title Multimodal AI Companion Launcher
echo ============================================================
echo         Starting Multimodal AI Companion System
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"

:: Determine base directory (handles both D:\AI ML Project and workspace folder)
if exist "%SCRIPT_DIR%backend\venv\Scripts\python.exe" (
    set "BASE_DIR=%SCRIPT_DIR%"
) else if exist "D:\AI ML Project\backend\venv\Scripts\python.exe" (
    set "BASE_DIR=D:\AI ML Project\"
) else (
    echo [ERROR] Could not locate backend at %SCRIPT_DIR% or D:\AI ML Project\
    pause
    exit /b 1
)

set "BACKEND_DIR=%BASE_DIR%backend"
set "FRONTEND_DIR=%BASE_DIR%frontend"

echo [1/3] Starting FastAPI Backend on http://localhost:8000 ...
start "AI Companion - Backend (FastAPI)" cmd /k "cd /d "%BACKEND_DIR%" && "venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Starting Vite Frontend on http://localhost:5173 ...
start "AI Companion - Frontend (Vite)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo [3/3] Waiting for servers to initialize...
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo   Services are online!
echo   - Web App UI : http://localhost:5173
echo   - API Docs   : http://localhost:8000/docs
echo ============================================================
echo.
echo Opening browser to http://localhost:5173 ...
start http://localhost:5173

echo.
echo Press any key to exit this launcher window (servers will continue running).
pause >nul
