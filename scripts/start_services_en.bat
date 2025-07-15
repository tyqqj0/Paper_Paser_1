@echo off
chcp 65001 > nul
cls

echo ===========================================
echo Literature Parser Backend - Quick Start
echo ===========================================
echo Starting production environment...
echo Services: API, Worker, MongoDB, Redis, GROBID
echo.

docker-compose up -d --build

echo.
echo ===========================================
echo Production environment started!
echo.
echo Service URLs:
echo   API Documentation:  http://localhost:8000/docs
echo   API Health Check:   http://localhost:8000/api/health
echo.
echo View logs: docker-compose logs -f [service_name]
echo Stop services: docker-compose down
echo.
echo Waiting for services to start...
echo   MongoDB and Redis need some time to initialize
echo   GROBID may take 1-2 minutes to download models on first start
echo.

echo Checking service status...
for /L %%i in (1,1,30) do (
    echo Waiting for API service... (%%i/30^)
    timeout /t 2 /nobreak > nul
    curl -s http://localhost:8000/api/health > nul 2>&1
    if !errorlevel! equ 0 (
        echo.
        echo ✓ API service is ready!
        echo ✓ Visit http://localhost:8000/docs to test the API
        goto :success
    )
)

echo.
echo Services are starting... This may take a few more minutes.
echo Check status with: docker-compose ps
echo Check logs with: docker-compose logs api

:success
echo.
echo Press any key to exit...
pause > nul 