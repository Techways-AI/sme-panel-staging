@echo off
REM ============================================
REM Start FastAPI Server Locally
REM ============================================
echo.
echo ============================================
echo Starting FastAPI Server Locally
echo ============================================
echo.

cd api

echo Checking if virtual environment exists...
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Using system Python.
)

echo.
echo Installing/updating dependencies...
pip install -r requirements.txt

echo.
echo Starting server on http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn app.main:app --reload --port 8000

pause

