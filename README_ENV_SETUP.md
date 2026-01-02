# 📝 Setting Up READ_ONLY_MODE in .env

## The Problem
Your `.env` file either doesn't exist or `READ_ONLY_MODE` is not set correctly.

## Solution

### Step 1: Create/Edit the .env file

Create or edit `api/.env` and add this line:

```
READ_ONLY_MODE=true
```

### Step 2: Verify it's working

Run this to check:
```powershell
cd api
python -c "from app.config.settings import READ_ONLY_MODE; print(f'READ_ONLY_MODE = {READ_ONLY_MODE}')"
```

Should show: `READ_ONLY_MODE = True`

### Step 3: Restart your server

After setting `READ_ONLY_MODE=true` in `.env`, restart your server:

```powershell
cd api
uvicorn app.main:app --reload --port 8001
```

---

## Quick Fix Script

Or use the provided script that sets it as an environment variable:

```powershell
.\start_server_readonly.ps1
```

This bypasses the .env file and sets it directly.

---

## What You Should See

When the server starts with `READ_ONLY_MODE=true`, you should see in the logs:

```
⚠️ READ_ONLY_MODE is ENABLED - All write operations (POST/PUT/PATCH/DELETE) are blocked
```

And tests should show:
- ✅ GET requests: 200 OK
- ✅ POST/PUT/DELETE: 503 Service Unavailable (not 401!)

