# 🧪 Quick Test Guide - Read-Only Mode

## Step 1: Start the Server

Open **Terminal 1** (PowerShell):

```powershell
cd "C:\Users\shiva\Desktop\New folder (10)\sme-panel-staging\api"
uvicorn app.main:app --reload --port 8000
```

Wait until you see:
```
Uvicorn running on http://127.0.0.1:8000
```

## Step 2: Run Tests

Open **Terminal 2** (PowerShell):

```powershell
cd "C:\Users\shiva\Desktop\New folder (10)\sme-panel-staging\api"
python test_readonly.py
```

OR from the root directory:

```powershell
cd "C:\Users\shiva\Desktop\New folder (10)\sme-panel-staging"
python test_readonly.py
```

## Expected Results

✅ **GET requests** → Should return `200 OK`  
❌ **POST/PUT/DELETE** → Should return `503 Service Unavailable`

---

## Alternative: Manual Browser Test

1. Start server (Terminal 1)
2. Open browser: `http://localhost:8000/docs`
3. Try any POST/PUT/DELETE endpoint
4. Should see `503` error with message about read-only mode

---

## Quick Commands Summary

**Terminal 1 (Server):**
```powershell
cd api
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 (Tests):**
```powershell
cd api
python test_readonly.py
```









