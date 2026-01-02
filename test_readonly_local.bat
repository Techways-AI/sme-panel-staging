@echo off
REM ============================================
REM Test Read-Only Mode Locally
REM ============================================
echo.
echo ============================================
echo Testing Read-Only Mode Locally
echo ============================================
echo.
echo Make sure your server is running on http://localhost:8000
echo If not, start it with: uvicorn app.main:app --reload --port 8000
echo.
pause

echo.
echo [TEST 1] Testing GET request (should work)...
curl http://localhost:8000/health
echo.
echo.

echo [TEST 2] Testing POST request (should be blocked)...
curl -X POST http://localhost:8000/api/documents/upload ^
  -H "Content-Type: application/json" ^
  -d "{}"
echo.
echo.

echo [TEST 3] Testing PUT request (should be blocked)...
curl -X PUT http://localhost:8000/api/documents/123 ^
  -H "Content-Type: application/json" ^
  -d "{}"
echo.
echo.

echo [TEST 4] Testing DELETE request (should be blocked)...
curl -X DELETE http://localhost:8000/api/documents/123
echo.
echo.

echo [TEST 5] Testing health check (should work)...
curl http://localhost:8000/health/detailed
echo.
echo.

echo ============================================
echo Tests Complete!
echo ============================================
echo.
echo Expected Results:
echo   - GET requests: Should work (200 OK)
echo   - POST/PUT/DELETE: Should return 503 error
echo   - Health checks: Should work (200 OK)
echo.
pause

