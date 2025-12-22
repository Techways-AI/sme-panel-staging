#!/bin/bash

# Railway startup script for backend
set -e

echo "=== Backend Container Starting ==="
echo "Port: $PORT"
echo "Python path: $PYTHONPATH"
echo "Working directory: $(pwd)"
echo "Current user: $(whoami)"
echo "Environment variables:"
env | grep -E "(PORT|PYTHON|ENV)" || echo "No relevant env vars found"

# Check if we're in production
if [ "$RAILWAY_ENVIRONMENT" = "production" ] || [ "$ENV" = "production" ]; then
    echo "Running in PRODUCTION mode - disabling reload"
    RELOAD_FLAG=""
else
    echo "Running in DEVELOPMENT mode - enabling reload"
    RELOAD_FLAG="--reload"
fi

# Ensure we're in the correct working directory
if [ ! -f "app/main.py" ]; then
    echo "WARNING: app/main.py not found in current directory, checking if we need to cd to backend"
    if [ -d "backend" ] && [ -f "backend/app/main.py" ]; then
        echo "Changing to backend directory..."
        cd backend
        echo "New working directory: $(pwd)"
    else
        echo "ERROR: Cannot find app/main.py in current directory or backend subdirectory"
        ls -la
        exit 1
    fi
fi

# Ensure PORT is set
if [ -z "$PORT" ]; then
    echo "WARNING: PORT environment variable not set, using default 8000"
    export PORT=8000
fi

# Optional shim: if Railway public networking targets 8000 but PORT differs,
# forward traffic from 8000 -> $PORT so the app still responds.
if [ "$PORT" != "8000" ]; then
    echo "Detected PORT=$PORT but public networking may point to 8000."
    echo "Starting TCP forward 8000 -> $PORT using socat..."
    socat TCP-LISTEN:8000,fork,reuseaddr TCP:127.0.0.1:$PORT &
    FORWARD_PID=$!
    echo "socat running with PID $FORWARD_PID"
fi

echo "Starting uvicorn on port $PORT..."
echo "Final working directory: $(pwd)"
echo "Checking if app/main.py exists: $(ls -la app/main.py 2>/dev/null || echo 'NOT FOUND')"

# Test import before starting uvicorn
echo "Testing Python imports..."
python -c "import app.main; print('✓ Main module imports successfully')" || {
    echo "✗ Import test failed - checking for syntax errors..."
    python -m py_compile app/main.py
    echo "✓ Syntax check passed - trying to identify import issue..."
    python -c "import app.main" 2>&1 | head -20
    exit 1
}

# Start the FastAPI application
echo "Starting uvicorn with command: uvicorn app.main:app --host 0.0.0.0 --port $PORT $RELOAD_FLAG"
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT $RELOAD_FLAG
