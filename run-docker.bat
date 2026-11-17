@echo off
REM ==============================================================================
REM 24FPS Forensic Platform - Docker Launcher for Windows 11 / 10
REM ==============================================================================
TITLE 24FPS Forensic Analysis Platform Launcher
COLOR 0A

echo ======================================================
echo     24FPS Forensic Analysis Platform Docker Setup     
echo ======================================================
echo.

REM 1. Verify Docker CLI is accessible
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [-] Error: 'docker' was not found in PATH.
    echo     Please make sure Docker Desktop for Windows is installed.
    echo     Download link: https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)

REM 2. Check if Docker daemon / Docker Desktop is running
docker info >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [-] Docker Desktop is not running!
    echo     Please launch Docker Desktop from your Start menu and wait
    echo     until it says "Engine running" in the bottom-left corner.
    echo.
    pause
    exit /b 1
)

REM 3. Ensure host data directories exist
if not exist "backend\data\evidence" mkdir "backend\data\evidence"
if not exist "backend\data\artifacts" mkdir "backend\data\artifacts"
if not exist "backend\data\reports" mkdir "backend\data\reports"
if not exist "backend\data\temp" mkdir "backend\data\temp"
if not exist "backend\data\logs" mkdir "backend\data\logs"
if not exist "backend\data\models" mkdir "backend\data\models"

echo [+] Building and starting 24FPS containers...
docker compose up --build -d

if %ERRORLEVEL% neq 0 (
    echo [-] Docker compose failed to start. Review error messages above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ======================================================
echo     24FPS PLATFORM IS RUNNING!                        
echo ======================================================
echo   Frontend Application: http://localhost:3000
echo   Backend API / Docs:   http://localhost:8000/docs
echo   Health Endpoint:      http://localhost:8000/api/v1/health
echo.
echo   Default Admin Credentials:
echo     Username: admin
echo     Password: admin
echo ======================================================
echo   Useful Commands:
echo     View live logs:      docker compose logs -f
echo     Stop containers:     docker compose down
echo     Restart containers:  docker compose restart
echo ======================================================
echo.

echo [+] Opening web portal in browser...
start http://localhost:3000

pause
