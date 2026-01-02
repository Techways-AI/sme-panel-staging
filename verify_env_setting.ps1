# Verify READ_ONLY_MODE setting in .env file
Write-Host "Checking .env file for READ_ONLY_MODE..." -ForegroundColor Cyan
Write-Host ""

$envFile = "api\.env"
if (Test-Path $envFile) {
    Write-Host "Found .env file at: $envFile" -ForegroundColor Green
    Write-Host ""
    Write-Host "Lines 60-62:" -ForegroundColor Yellow
    $lines = Get-Content $envFile
    if ($lines.Count -ge 62) {
        Write-Host "Line 60: $($lines[59])" -ForegroundColor White
        Write-Host "Line 61: $($lines[60])" -ForegroundColor White
        Write-Host "Line 62: $($lines[61])" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "Searching for READ_ONLY_MODE:" -ForegroundColor Yellow
    $readOnlyLine = Get-Content $envFile | Select-String "READ_ONLY"
    if ($readOnlyLine) {
        Write-Host $readOnlyLine -ForegroundColor Green
        Write-Host ""
        if ($readOnlyLine -match "READ_ONLY_MODE\s*=\s*true" -or $readOnlyLine -match "READ_ONLY_MODE=true") {
            Write-Host "✅ READ_ONLY_MODE is set to 'true'" -ForegroundColor Green
        } else {
            Write-Host "⚠️ READ_ONLY_MODE might not be set correctly" -ForegroundColor Yellow
            Write-Host "   Expected: READ_ONLY_MODE=true" -ForegroundColor Yellow
            Write-Host "   Found: $readOnlyLine" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ READ_ONLY_MODE not found in .env file" -ForegroundColor Red
        Write-Host ""
        Write-Host "Add this line to api/.env:" -ForegroundColor Cyan
        Write-Host "READ_ONLY_MODE=true" -ForegroundColor White
    }
} else {
    Write-Host "❌ .env file not found at: $envFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "Creating .env file with READ_ONLY_MODE=true..." -ForegroundColor Yellow
    "READ_ONLY_MODE=true" | Out-File -FilePath $envFile -Encoding utf8
    Write-Host "✅ Created .env file" -ForegroundColor Green
}

Write-Host ""
Write-Host "Verifying Python can read it:" -ForegroundColor Cyan
cd api
python -c "from app.config.settings import READ_ONLY_MODE; print(f'READ_ONLY_MODE = {READ_ONLY_MODE}')"

