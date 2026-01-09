@echo off
REM ============================================
REM STEP 2: Export AWS RDS Database
REM ============================================
echo.
echo ============================================
echo Exporting AWS RDS Database to aws_backup.dump
echo ============================================
echo.

REM AWS RDS Connection Details (from your connection string)
set AWS_HOST=durranisdb.cv46gqs82fzh.ap-south-1.rds.amazonaws.com
set AWS_USER=postgres
set AWS_DB=postgres
set AWS_PORT=5432

REM PostgreSQL bin path - adjust if needed
set PG_PATH=C:\Program Files\PostgreSQL\18\bin

echo AWS RDS Endpoint: %AWS_HOST%
echo Database: %AWS_DB%
echo Username: %AWS_USER%
echo.
echo Running pg_dump...
echo You will be prompted for the password: Dur!Ns_2025
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
    echo [ERROR] pg_dump failed!
    echo Please check:
    echo 1. PostgreSQL is installed and pg_dump.exe exists at: %PG_PATH%
    echo 2. AWS RDS security group allows your IP address
    echo 3. Password is correct: Dur!Ns_2025
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo [SUCCESS] Database dump created!
echo ============================================
echo.
echo File: aws_backup.dump
echo.

REM Check file size
for %%A in (aws_backup.dump) do set SIZE=%%~zA
echo File size: %SIZE% bytes

if %SIZE% EQU 0 (
    echo [WARNING] Dump file is empty!
    pause
    exit /b 1
)

echo.
echo Next step: Run STEP 3 to verify the dump file
echo Command: dir aws_backup.dump
echo.
pause







