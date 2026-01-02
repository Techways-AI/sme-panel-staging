# Start Server with Read-Only Mode Enabled
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Starting Server with Read-Only Mode Enabled" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location api

# Set environment variable for this PowerShell session
$env:READ_ONLY_MODE = "true"

Write-Host "READ_ONLY_MODE is set to: $env:READ_ONLY_MODE" -ForegroundColor Green
Write-Host ""
Write-Host "Starting uvicorn server on port 8001..." -ForegroundColor Yellow
Write-Host ""

uvicorn app.main:app --reload --port 8001

