# AWS RDS → Railway PostgreSQL Migration Steps

## ✅ STEP 1 — PUT APP IN READ-ONLY MODE

**Status:** ✅ **COMPLETED** - Read-only mode middleware has been implemented.

To enable read-only mode, set this environment variable:

```bash
READ_ONLY_MODE=true
```

**What this does:**
- Blocks all POST, PUT, PATCH, DELETE requests
- Allows GET requests (read-only)
- Allows health check endpoints
- Returns 503 status with clear error message

**To enable:**
1. Set `READ_ONLY_MODE=true` in your `.env` file or Railway environment variables
2. Restart the application
3. Verify by trying to create/update/delete - should return 503 error

**To disable (after migration):**
1. Set `READ_ONLY_MODE=false` or remove the variable
2. Restart the application

---

## 📦 STEP 2 — EXPORT AWS RDS DATABASE

### ✅ Quick Option: Run the automated script
```bat
run_step2_export.bat
```

### Manual Option: Run this exact command

Run this in **Command Prompt** (Windows):

```bat
"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" ^
  -h durranisdb.cv46gqs82fzh.ap-south-1.rds.amazonaws.com ^
  -U postgres ^
  -p 5432 ^
  -d postgres ^
  -F c ^
  -b ^
  -v ^
  -f aws_backup.dump
```

**Password when prompted:** `Dur!Ns_2025`

**Parameters explained:**
- `-h`: AWS RDS endpoint hostname
- `-U`: Database username
- `-d`: Database name
- `-F c`: Custom format (compressed)
- `-b`: Include blobs
- `-v`: Verbose output
- `-f`: Output file name

➡️ **Enter AWS DB password when prompted.**

---

## ✅ STEP 3 — VERIFY DUMP FILE

```bat
dir aws_backup.dump
```

**Check:**
- ✔ File exists
- ✔ File size > 0 KB (should be several MB for a real database)

---

## 🚀 STEP 4 — RESTORE INTO RAILWAY POSTGRES

```bat
"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" ^
  -d "postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require" ^
  -v ^
  aws_backup.dump
```

**Note:** 
- ⚠️ Ignore warnings about roles/owners (these are normal)
- The restore may take several minutes depending on database size

---

## 🔑 STEP 5 — FIX PERMISSIONS

Connect to Railway database:

```bat
"C:\Program Files\PostgreSQL\18\bin\psql.exe" ^
"postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require"
```

Run these SQL commands inside psql:

```sql
ALTER SCHEMA public OWNER TO postgres;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;
```

Exit psql:

```sql
\q
```

---

## 🔍 STEP 6 — VERIFY DATA

Connect to Railway database again:

```bat
"C:\Program Files\PostgreSQL\18\bin\psql.exe" ^
"postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require"
```

Run verification queries:

```sql
-- List all tables
\dt

-- Count records in key tables
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM notes;
SELECT COUNT(*) FROM curriculum;
SELECT COUNT(*) FROM content_library;

-- Check table structure
\d users
\d notes
```

**Verify:**
- ✔ Tables exist
- ✔ Row counts match (or are close to) AWS RDS counts
- ✔ Table structures are correct

Exit:

```sql
\q
```

---

## 🔁 STEP 7 — SWITCH APPLICATION TO RAILWAY DB

Update `DATABASE_URL` environment variable to:

```
postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway
```

**Update in:**
1. **Local `.env` file** (if exists):
   ```
   DATABASE_URL=postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway
   ```

2. **Railway Environment Variables:**
   - Go to Railway dashboard
   - Select your service
   - Go to Variables tab
   - Update `DATABASE_URL` value

3. **CI/CD configuration** (if applicable)

**Note:** The database connection is configured in `api/app/config/database.py` and reads from `DATABASE_URL` environment variable.

---

## 🚢 STEP 8 — REDEPLOY APP

```bash
git add .
git commit -m "Switch database from AWS RDS to Railway"
git push
```

Railway will automatically redeploy. Monitor the deployment logs to ensure:
- ✔ Application starts successfully
- ✔ Database connection works
- ✔ No connection errors

---

## 🔓 STEP 9 — ENABLE WRITES AGAIN

1. **Disable read-only mode:**
   - Set `READ_ONLY_MODE=false` in Railway environment variables
   - OR remove the `READ_ONLY_MODE` variable
   - Restart the application

2. **Verify writes work:**
   - Try creating a test record
   - Try updating a record
   - Try deleting a test record

---

## ✅ STEP 10 — FINAL CHECK

**Test all operations:**
1. ✅ Create a new record (POST)
2. ✅ Update an existing record (PUT/PATCH)
3. ✅ Delete a test record (DELETE)
4. ✅ Read records (GET)
5. ✅ Restart the application once
6. ✅ Check application logs for any errors

**Monitor for 24-48 hours:**
- Check application logs regularly
- Monitor database connection stability
- Verify all features work correctly

---

## ❗ IMPORTANT NOTES

### ⚠️ DO NOT DO YET:
- ❌ Delete AWS RDS instance
- ❌ Modify AWS RDS database
- ❌ Remove AWS RDS backups

### ✅ WAIT 24-48 HOURS:
- Monitor Railway database performance
- Verify all application features work
- Check for any data inconsistencies
- Only then consider decommissioning AWS RDS

---

## 🆘 TROUBLESHOOTING

### Issue: pg_dump fails with connection error
- Check AWS RDS security group allows your IP
- Verify endpoint, username, and database name
- Check if password is correct

### Issue: pg_restore fails with permission errors
- Run STEP 5 (Fix Permissions) again
- Check if you're using the correct connection string

### Issue: Application can't connect to Railway
- Verify DATABASE_URL is set correctly
- Check Railway database is running
- Verify connection string includes `?sslmode=require`

### Issue: Read-only mode not working
- Check `READ_ONLY_MODE=true` is set
- Restart the application
- Check application logs for read-only mode message

---

## 📝 CURRENT STATUS

- ✅ STEP 1: Read-only mode implemented
- ⏳ STEP 2: Ready to run pg_dump
- ⏳ STEP 3-10: Pending

**Next Action:** Run STEP 2 (pg_dump) with your AWS RDS credentials.

