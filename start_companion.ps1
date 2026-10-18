Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "         Starting Multimodal AI Companion System            " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$baseDir = "D:\AI ML Project"
if (-not (Test-Path "$baseDir\backend\venv\Scripts\python.exe")) {
    $baseDir = $PSScriptRoot
}

$backendDir = Join-Path $baseDir "backend"
$frontendDir = Join-Path $baseDir "frontend"
$pythonExe = Join-Path $backendDir "venv\Scripts\python.exe"

Write-Host "`n[1/3] Starting FastAPI Backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backendDir'; & '$pythonExe' -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "[2/3] Starting Vite Frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev"

Start-Sleep -Seconds 3

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  Services are online!" -ForegroundColor Cyan
Write-Host "  - Web App UI : http://localhost:5173" -ForegroundColor Yellow
Write-Host "  - API Docs   : http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "============================================================`n" -ForegroundColor Cyan

Start-Process "http://localhost:5173"
