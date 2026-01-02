# Setup READ_ONLY_MODE in .env file
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Setting up READ_ONLY_MODE in .env file" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$envFile = "api\.env"

# Check if .env exists
if (Test-Path $envFile) {
    Write-Host "Found .env file at: $envFile" -ForegroundColor Green
    Write-Host ""
    
    # Check if READ_ONLY_MODE already exists
    $content = Get-Content $envFile
    $hasReadOnly = $content | Select-String -Pattern "^READ_ONLY_MODE"
    
    if ($hasReadOnly) {
        Write-Host "READ_ONLY_MODE found in .env:" -ForegroundColor Yellow
        Write-Host $hasReadOnly -ForegroundColor White
        Write-Host ""
        Write-Host "Updating to READ_ONLY_MODE=true..." -ForegroundColor Yellow
        
        # Replace the line
        $newContent = $content | ForEach-Object {
            if ($_ -match "^READ_ONLY_MODE") {
                "READ_ONLY_MODE=true"
            } else {
                $_
            }
        }
        $newContent | Set-Content $envFile -Encoding utf8
        Write-Host "✅ Updated READ_ONLY_MODE=true" -ForegroundColor Green
    } else {
        Write-Host "Adding READ_ONLY_MODE=true to .env..." -ForegroundColor Yellow
        Add-Content -Path $envFile -Value "READ_ONLY_MODE=true" -Encoding utf8
        Write-Host "✅ Added READ_ONLY_MODE=true" -ForegroundColor Green
    }
} else {
    Write-Host ".env file not found. Creating it..." -ForegroundColor Yellow
    "READ_ONLY_MODE=true" | Out-File -FilePath $envFile -Encoding utf8
    Write-Host "✅ Created .env file with READ_ONLY_MODE=true" -ForegroundColor Green
}

Write-Host ""
Write-Host "Verifying..." -ForegroundColor Cyan
Write-Host ""

# Verify it works
Set-Location api
python -c "from app.config.settings import READ_ONLY_MODE; print('READ_ONLY_MODE =', READ_ONLY_MODE)"
Set-Location ..

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Done! Restart your server to apply changes." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

