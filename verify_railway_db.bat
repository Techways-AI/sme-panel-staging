@echo off
REM ============================================
REM Verify Railway Database Migration
REM ============================================
echo.
echo ============================================
echo Railway Database Verification
echo ============================================
echo.

set /p PG_PATH="PostgreSQL bin path (e.g., C:\Program Files\PostgreSQL\18\bin): "

echo.
echo Connecting to Railway database...
echo.

echo \dt > verify_queries.sql
echo SELECT COUNT(*) as users_count FROM users; >> verify_queries.sql
echo SELECT COUNT(*) as notes_count FROM notes; >> verify_queries.sql
echo SELECT COUNT(*) as curriculum_count FROM curriculum; >> verify_queries.sql
echo SELECT COUNT(*) as content_library_count FROM content_library; >> verify_queries.sql

"%PG_PATH%\psql.exe" ^
  "postgresql://postgres:aWpxrNtSQmYmEcuuTklKHaFMAwYDxZjt@mainline.proxy.rlwy.net:33207/railway?sslmode=require" ^
  -f verify_queries.sql

del verify_queries.sql

echo.
echo ============================================
echo Verification Complete!
echo ============================================
echo.
echo Compare the counts above with your AWS RDS database.
echo If counts match, migration was successful!
echo.
pause

