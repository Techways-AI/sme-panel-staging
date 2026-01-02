# 🧪 Testing Read-Only Mode Locally

## Step 1: Set READ_ONLY_MODE in .env

Make sure your `api/.env` file has:
```
READ_ONLY_MODE=true
```

## Step 2: Start the Application Locally

Open a terminal in the `api` folder and run:

```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Start the FastAPI server
uvicorn app.main:app --reload --port 8000
```

Or if you're using Python directly:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

The server will start at: `http://localhost:8000`

## Step 3: Test Read-Only Mode

### Test 1: GET Request (Should Work ✅)
```bash
curl http://localhost:8000/health
```

Expected: Should return `{"status": "healthy", ...}`

### Test 2: POST Request (Should Be Blocked ❌)
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Content-Type: application/json" \
  -d "{}"
```

Expected: Should return `503` with error message:
```json
{
  "error": "Service temporarily in read-only mode",
  "message": "The application is currently in read-only mode for database migration. Write operations are disabled.",
  "read_only_mode": true,
  "allowed_methods": ["GET", "OPTIONS"]
}
```

### Test 3: PUT Request (Should Be Blocked ❌)
```bash
curl -X PUT http://localhost:8000/api/documents/123 \
  -H "Content-Type: application/json" \
  -d "{}"
```

Expected: Should return `503` error

### Test 4: DELETE Request (Should Be Blocked ❌)
```bash
curl -X DELETE http://localhost:8000/api/documents/123
```

Expected: Should return `503` error

### Test 5: Health Check Endpoints (Should Work ✅)
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
curl http://localhost:8000/test
```

Expected: All should work (these are allowed in read-only mode)

## Step 4: Check Logs

In your terminal where the server is running, you should see:
```
⚠️ READ_ONLY_MODE is ENABLED - All write operations (POST/PUT/PATCH/DELETE) are blocked
```

## Step 5: Disable Read-Only Mode

To test normal operation:
1. Set `READ_ONLY_MODE=false` in `.env` (or remove it)
2. Restart the server
3. POST/PUT/DELETE should work again

---

## Quick Test Script

Run `test_readonly_local.bat` (Windows) or use the commands above.

