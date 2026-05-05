@echo off
REM ============================================================
REM  OTP Registration System — Start Script (Windows)
REM  Starts FastAPI backend + React frontend in separate windows
REM ============================================================

echo.
echo  Starting OTP Registration System...
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:5173
echo.

REM ── Backend ────────────────────────────────────────────────
start "FastAPI Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --reload --port 8000"

REM ── Frontend ───────────────────────────────────────────────
start "React Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo  Both servers starting in new windows.
echo  Press any key to exit this launcher.
pause > nul
