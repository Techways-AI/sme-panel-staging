# Quick script to check if server is running
Write-Host "Checking if server is running on port 8001..." -ForegroundColor Yellow

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -TimeoutSec 3 -UseBasicParsing
    Write-Host "✅ Server IS running on port 8001!" -ForegroundColor Green
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($response.Content)" -ForegroundColor Green
} catch {
    Write-Host "❌ Server is NOT running on port 8001" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start the server:" -ForegroundColor Yellow
    Write-Host "  cd api" -ForegroundColor Cyan
    Write-Host "  uvicorn app.main:app --reload --port 8001" -ForegroundColor Cyan
}






