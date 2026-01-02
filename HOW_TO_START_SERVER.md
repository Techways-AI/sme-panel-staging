# 🚀 How to Start Server for Testing

## Step 1: Make sure READ_ONLY_MODE is enabled

Check your `api/.env` file has:
```
READ_ONLY_MODE=true
```

## Step 2: Start the Server

Open a **new PowerShell terminal** and run:

```powershell
cd "C:\Users\shiva\Desktop\New folder (10)\sme-panel-staging\api"
uvicorn app.main:app --reload --port 8001
```

**Wait until you see:**
```
INFO:     Uvicorn running on https://sme-panel-staging-production.up.railway.app (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Step 3: Verify Server is Running

In a **different PowerShell terminal**, run:

```powershell
cd "C:\Users\shiva\Desktop\New folder (10)\sme-panel-staging"
.\check_server.ps1
```

OR manually check:
```powershell
Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing
```

## Step 4: Run Tests

Once server is confirmed running, in the same terminal:

```powershell
cd api
python test_readonly.py
```

---

## Troubleshooting

### Server won't start?
- Check if port 8001 is already in use
- Make sure you're in the `api` folder
- Check for Python/uvicorn installation: `pip install uvicorn fastapi`

### Connection timeout?
- Make sure server actually started (check the terminal where you ran uvicorn)
- Try a different port: `--port 8002`
- Check Windows Firewall settings

### Port already in use?
Change the port:
```powershell
uvicorn app.main:app --reload --port 8002
```
Then update `BASE_URL` in `test_readonly.py` to `http://localhost:8002`

