@echo off
REM ============================================
REM Start Server with Read-Only Mode Enabled
REM ============================================
echo.
echo Starting server with READ_ONLY_MODE=true
echo.

cd api

REM Set environment variable for this session
set READ_ONLY_MODE=true

echo READ_ONLY_MODE is set to: %READ_ONLY_MODE%
echo.
echo Starting uvicorn server...
echo.

uvicorn app.main:app --reload --port 8001

pause

