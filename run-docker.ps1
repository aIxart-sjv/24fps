# ==============================================================================
# 24FPS Forensic Platform - Docker Launcher for Windows PowerShell
# ==============================================================================

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "    24FPS Forensic Analysis Platform Docker Setup     " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verify Docker CLI is accessible
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[-] Error: 'docker' was not found in PATH." -ForegroundColor Red
    Write-Host "    Please make sure Docker Desktop for Windows is installed." -ForegroundColor Yellow
    Write-Host "    Download link: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    Exit 1
}

# 2. Check if Docker daemon is running
docker info 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Docker Desktop is not running!" -ForegroundColor Red
    Write-Host "    Please launch Docker Desktop and wait until it says 'Engine running'." -ForegroundColor Yellow
    Exit 1
}

# 3. Ensure host data directories exist
$dataDirs = @(
    "backend/data/evidence",
    "backend/data/artifacts",
    "backend/data/reports",
    "backend/data/temp",
    "backend/data/logs",
    "backend/data/models"
)

foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

Write-Host "[+] Building and starting 24FPS containers..." -ForegroundColor Green
docker compose up --build -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Docker Compose failed to start. Review errors above." -ForegroundColor Red
    Exit $LASTEXITCODE
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "    24FPS PLATFORM IS RUNNING!                        " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Frontend Application: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API / Docs:   http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Health Endpoint:      http://localhost:8000/api/v1/health" -ForegroundColor White
Write-Host ""
Write-Host "  Default Admin Credentials:" -ForegroundColor Yellow
Write-Host "    Username: admin" -ForegroundColor Yellow
Write-Host "    Password: admin" -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Useful Commands:" -ForegroundColor Gray
Write-Host "    View live logs:      docker compose logs -f" -ForegroundColor Gray
Write-Host "    Stop containers:     docker compose down" -ForegroundColor Gray
Write-Host "    Restart containers:  docker compose restart" -ForegroundColor Gray
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://localhost:3000"
