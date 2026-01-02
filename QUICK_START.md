# 🚀 Quick Start - Database Migration

## Your AWS RDS Connection Details
- **Host:** `durranisdb.cv46gqs82fzh.ap-south-1.rds.amazonaws.com`
- **User:** `postgres`
- **Database:** `postgres`
- **Password:** `Dur!Ns_2025`
- **Port:** `5432`

## Your Railway Connection String
```
postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require
```

---

## ⚡ Fastest Way: Run All Steps Automatically

### Option 1: Complete Automated Migration (Steps 2-5)
```bat
run_all_migration_steps.bat
```

This will:
1. ✅ Export AWS RDS database
2. ✅ Verify dump file
3. ✅ Restore to Railway
4. ✅ Fix permissions

**Note:** You'll be prompted for password: `Dur!Ns_2025`

---

## 📋 Step-by-Step Manual Process

### STEP 1: Enable Read-Only Mode ✅ (Already Done)
Set in Railway environment variables:
```
READ_ONLY_MODE=true
```

### STEP 2: Export Database
```bat
run_step2_export.bat
```
OR manually:
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
Password: `Dur!Ns_2025`

### STEP 3: Verify Dump
```bat
dir aws_backup.dump
```

### STEP 4: Restore to Railway
```bat
"C:\Program Files\PostgreSQL\18\bin\pg_restore.exe" ^
  -d "postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require" ^
  -v ^
  aws_backup.dump
```

### STEP 5: Fix Permissions
```bat
"C:\Program Files\PostgreSQL\18\bin\psql.exe" ^
"postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require"
```

Then run in psql:
```sql
ALTER SCHEMA public OWNER TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;
\q
```

### STEP 6: Verify Data
```bat
verify_railway_db.bat
```

### STEP 7: Update DATABASE_URL in Railway
Set in Railway environment variables:
```
DATABASE_URL=postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require
```

### STEP 8: Redeploy
```bash
git add .
git commit -m "Switch database from AWS RDS to Railway"
git push
```

### STEP 9: Disable Read-Only Mode
Set in Railway:
```
READ_ONLY_MODE=false
```

### STEP 10: Test Everything
- Create a record
- Update a record
- Delete a record
- Check logs

---

## 🎯 Recommended: Use Automated Script

Just run:
```bat
run_all_migration_steps.bat
```

Then follow Steps 6-10 manually.

---

## ⚠️ Important Notes

1. **PostgreSQL Path:** If your PostgreSQL is not at `C:\Program Files\PostgreSQL\18\bin`, edit the `.bat` files and update the `PG_PATH` variable.

2. **AWS Security Group:** Make sure your AWS RDS security group allows connections from your IP address.

3. **Wait 24-48 hours** before deleting AWS RDS - monitor Railway first!



