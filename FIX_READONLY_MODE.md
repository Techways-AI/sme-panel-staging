# 🔧 Fix: READ_ONLY_MODE Not Working

## Problem
The `READ_ONLY_MODE` is showing as `False` even though you set it in `.env`.

## Solution: Set Environment Variable

### Option 1: Use the PowerShell Script (Recommended)

```powershell
.\start_server_readonly.ps1
```

This script sets `READ_ONLY_MODE=true` and starts the server.

### Option 2: Set Manually in PowerShell

```powershell
cd api
$env:READ_ONLY_MODE = "true"
uvicorn app.main:app --reload --port 8001
```

### Option 3: Set in .env File (if it exists)

Make sure your `api/.env` file has:
```
READ_ONLY_MODE=true
```

Then verify it's being loaded:
```powershell
cd api
python -c "from app.config.settings import READ_ONLY_MODE; print(f'READ_ONLY_MODE = {READ_ONLY_MODE}')"
```

Should show: `READ_ONLY_MODE = True`

---

## Quick Test

1. **Start server with read-only mode:**
   ```powershell
   .\start_server_readonly.ps1
   ```

2. **In another terminal, run tests:**
   ```powershell
   cd api
   python test_readonly.py
   ```

3. **Expected:** All tests should pass (POST/PUT/DELETE should return 503)

---

## Verify It's Working

Check the server logs - you should see:
```
⚠️ READ_ONLY_MODE is ENABLED - All write operations (POST/PUT/PATCH/DELETE) are blocked
```

And when you try a POST request, you should get:
```json
{
  "error": "Service temporarily in read-only mode",
  "read_only_mode": true
}
```

Instead of:
```json
{
  "detail": "Authentication required..."
}
```

