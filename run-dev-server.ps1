# PowerShell script to set environment and start Django dev server with Poppler support

Write-Host "Setting up environment..." -ForegroundColor Green

$popplerPath = "C:\Release-26.02.0-0\poppler-26.02.0\Library\bin"
$env:PATH += ";$popplerPath"

Write-Host "Poppler path: $popplerPath"
try {
    $result = & pdftoppm -h 2>&1
    Write-Host "✓ Poppler available" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Poppler not found at expected location" -ForegroundColor Red
    Write-Host "Expected: $popplerPath" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

Write-Host ""
Write-Host "Running Django checks..." -ForegroundColor Green
Set-Location backend
python manage.py check
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Django check failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ Environment ready. Starting Django dev server..." -ForegroundColor Green
python manage.py runserver 0.0.0.0:8000
