@echo off
REM ============================================
REM AWS RDS to Railway PostgreSQL Migration Script
REM ============================================
echo.
echo ============================================
echo AWS RDS to Railway PostgreSQL Migration
echo ============================================
echo.

REM ============================================
REM STEP 2: Export AWS RDS Database
REM ============================================
echo [STEP 2] Exporting AWS RDS database...
echo.
echo Please enter your AWS RDS details:
echo.

set /p AWS_HOST="AWS RDS Endpoint (e.g., durranisdb.ap-south-1.rds.amazonaws.com): "
set /p AWS_USER="AWS DB Username (e.g., postgres): "
set /p AWS_DB="AWS DB Name (e.g., postgres): "
set /p PG_PATH="PostgreSQL bin path (e.g., C:\Program Files\PostgreSQL\18\bin): "

echo.
echo Running pg_dump...
echo.

"%PG_PATH%\pg_dump.exe" ^
  -h %AWS_HOST% ^
  -U %AWS_USER% ^
  -p 5432 ^
  -d %AWS_DB% ^
  -F c ^
  -b ^
  -v ^
  -f aws_backup.dump

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] pg_dump failed! Please check your credentials and try again.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Database dump created: aws_backup.dump
echo.

REM ============================================
REM STEP 3: Verify Dump File
REM ============================================
echo [STEP 3] Verifying dump file...
echo.

if not exist aws_backup.dump (
    echo [ERROR] Dump file not found!
    pause
    exit /b 1
)

for %%A in (aws_backup.dump) do set SIZE=%%~zA
echo File size: %SIZE% bytes

if %SIZE% EQU 0 (
    echo [ERROR] Dump file is empty!
    pause
    exit /b 1
)

echo [SUCCESS] Dump file verified!
echo.

REM ============================================
REM STEP 4: Restore into Railway
REM ============================================
echo [STEP 4] Restoring into Railway PostgreSQL...
echo.
echo This may take several minutes depending on database size...
echo.

"%PG_PATH%\pg_restore.exe" ^
  -d "postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require" ^
  -v ^
  aws_backup.dump

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] pg_restore completed with warnings (this is usually normal)
    echo Ignore warnings about roles/owners.
    echo.
) else (
    echo.
    echo [SUCCESS] Database restored to Railway!
    echo.
)

REM ============================================
REM STEP 5: Fix Permissions
REM ============================================
echo [STEP 5] Fixing permissions...
echo.
echo Connecting to Railway database to fix permissions...
echo.

echo ALTER SCHEMA public OWNER TO postgres; > fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres; >> fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres; >> fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres; >> fix_permissions.sql

"%PG_PATH%\psql.exe" ^
  "postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require" ^
  -f fix_permissions.sql

if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Permission fix may have failed. You may need to run STEP 5 manually.
) else (
    echo [SUCCESS] Permissions fixed!
)

del fix_permissions.sql

echo.
echo ============================================
echo Migration Steps 2-5 Complete!
echo ============================================
echo.
echo Next steps:
echo 1. Run STEP 6 manually to verify data
echo 2. Update DATABASE_URL in Railway environment variables
echo 3. Redeploy application
echo 4. Disable READ_ONLY_MODE
echo.
echo See MIGRATION_STEPS.md for detailed instructions.
echo.
pause

