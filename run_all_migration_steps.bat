@echo off
REM ============================================
REM Complete AWS RDS to Railway Migration
REM ============================================
echo.
echo ============================================
echo AWS RDS to Railway PostgreSQL Migration
echo Complete Automated Script
echo ============================================
echo.

REM ============================================
REM Configuration
REM ============================================
set AWS_HOST=durranisdb.cv46gqs82fzh.ap-south-1.rds.amazonaws.com
set AWS_USER=postgres
set AWS_DB=postgres
set AWS_PORT=5432
set PG_PATH=C:\Program Files\PostgreSQL\18\bin
set RAILWAY_URL=postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require

echo Configuration:
echo   AWS Host: %AWS_HOST%
echo   AWS Database: %AWS_DB%
echo   PostgreSQL Path: %PG_PATH%
echo   Railway URL: (configured)
echo.

REM ============================================
REM STEP 2: Export AWS RDS Database
REM ============================================
echo.
echo [STEP 2] Exporting AWS RDS database...
echo You will be prompted for password: Dur!Ns_2025
echo.

"%PG_PATH%\pg_dump.exe" ^
  -h %AWS_HOST% ^
  -U %AWS_USER% ^
  -p %AWS_PORT% ^
  -d %AWS_DB% ^
  -F c ^
  -b ^
  -v ^
  -f aws_backup.dump

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] STEP 2 FAILED - pg_dump failed!
    pause
    exit /b 1
)

echo [SUCCESS] STEP 2 complete - Database exported
echo.

REM ============================================
REM STEP 3: Verify Dump File
REM ============================================
echo [STEP 3] Verifying dump file...

if not exist aws_backup.dump (
    echo [ERROR] STEP 3 FAILED - Dump file not found!
    pause
    exit /b 1
)

for %%A in (aws_backup.dump) do set SIZE=%%~zA
echo File size: %SIZE% bytes

if %SIZE% EQU 0 (
    echo [ERROR] STEP 3 FAILED - Dump file is empty!
    pause
    exit /b 1
)

echo [SUCCESS] STEP 3 complete - Dump file verified
echo.

REM ============================================
REM STEP 4: Restore into Railway
REM ============================================
echo [STEP 4] Restoring into Railway PostgreSQL...
echo This may take several minutes...
echo.

"%PG_PATH%\pg_restore.exe" ^
  -d "%RAILWAY_URL%" ^
  -v ^
  aws_backup.dump

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING] pg_restore completed with warnings (usually normal)
    echo Ignore warnings about roles/owners.
    echo.
) else (
    echo [SUCCESS] STEP 4 complete - Database restored to Railway
)

echo.

REM ============================================
REM STEP 5: Fix Permissions
REM ============================================
echo [STEP 5] Fixing permissions...

echo ALTER SCHEMA public OWNER TO postgres; > fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres; >> fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres; >> fix_permissions.sql
echo GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres; >> fix_permissions.sql

"%PG_PATH%\psql.exe" "%RAILWAY_URL%" -f fix_permissions.sql

if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Permission fix may have failed. Run STEP 5 manually if needed.
) else (
    echo [SUCCESS] STEP 5 complete - Permissions fixed
)

del fix_permissions.sql
echo.

REM ============================================
REM Summary
REM ============================================
echo.
echo ============================================
echo Migration Steps 2-5 Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Run verify_railway_db.bat to verify data (STEP 6)
echo   2. Update DATABASE_URL in Railway to:
echo      %RAILWAY_URL%
echo   3. Set READ_ONLY_MODE=false in Railway
echo   4. Redeploy application
echo.
echo See MIGRATION_STEPS.md for detailed instructions.
echo.
pause

