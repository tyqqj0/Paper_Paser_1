@echo off
setlocal enabledelayedexpansion

REM Literature Parser Backend - Windows One-Click Startup Script
REM This script will start the complete literature parsing ecosystem

echo.
echo 🚀 Literature Parser Backend - One-Click Startup
echo ===============================================

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not running, please start Docker Desktop first
    pause
    exit /b 1
)

REM Check if Docker Compose is available
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ docker-compose is not installed, please install Docker Compose first
    pause
    exit /b 1
)

REM Create .env file (if it doesn't exist)
if not exist .env (
    echo 📝 Creating .env configuration file...
    (
        echo # Literature Parser Backend Configuration
        echo LITERATURE_PARSER_BACKEND_VERSION=latest
        echo LITERATURE_PARSER_BACKEND_HOST=0.0.0.0
        echo LITERATURE_PARSER_BACKEND_PORT=8000
        echo LITERATURE_PARSER_BACKEND_LOG_LEVEL=INFO
        echo LITERATURE_PARSER_BACKEND_RELOAD=False
        echo.
        echo # Database Configuration
        echo LITERATURE_PARSER_BACKEND_DB_HOST=literature_parser_backend-db
        echo LITERATURE_PARSER_BACKEND_DB_PORT=27017
        echo LITERATURE_PARSER_BACKEND_DB_USER=literature_parser_backend
        echo LITERATURE_PARSER_BACKEND_DB_PASS=literature_parser_backend
        echo LITERATURE_PARSER_BACKEND_DB_BASE=admin
        echo.
        echo # Redis Configuration
        echo REDIS_URL=redis://redis:6379/0
        echo.
        echo # External Services
        echo GROBID_URL=http://grobid:8070
        echo CROSSREF_EMAIL=literature-parser@example.com
        echo.
        echo # Celery Configuration
        echo CELERY_BROKER_URL=redis://redis:6379/0
        echo CELERY_RESULT_BACKEND=redis://redis:6379/0
        echo CELERY_TASK_SERIALIZER=json
        echo CELERY_RESULT_SERIALIZER=json
        echo CELERY_ACCEPT_CONTENT=json
        echo CELERY_TIMEZONE=UTC
        echo CELERY_ENABLE_UTC=True
    ) > .env
    echo ✅ .env file created
)

REM Check startup mode
set MODE=%1
if "%MODE%"=="" set MODE=production

if "%MODE%"=="dev" (
    set MODE=development
)

if "%MODE%"=="development" (
    echo 🔧 Starting development environment...
    echo Included services: API, Worker, MongoDB, Redis, GROBID, Redis Commander, Mongo Express
    
    REM Start development environment
    docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build -d
    
    echo.
    echo 🎉 Development environment started successfully!
    echo.
    echo 📋 Service addresses:
    echo   • API Documentation:  http://localhost:8000/docs
    echo   • API Health Check:   http://localhost:8000/api/health
    echo   • Redis Commander:    http://localhost:8081
    echo   • Mongo Express:      http://localhost:8082
    echo   • GROBID:             http://localhost:8070
    echo.
    echo 🔍 View logs: docker-compose logs -f [service_name]
    echo 🛑 Stop services: docker-compose down
    
) else (
    echo 🏭 Starting production environment...
    echo Included services: API, Worker, MongoDB, Redis, GROBID
    
    REM Start production environment
    docker-compose up --build -d
    
    echo.
    echo 🎉 Production environment started successfully!
    echo.
    echo 📋 Service addresses:
    echo   • API Documentation:  http://localhost:8000/docs
    echo   • API Health Check:   http://localhost:8000/api/health
    echo.
    echo 🔍 View logs: docker-compose logs -f [service_name]
    echo 🛑 Stop services: docker-compose down
)

echo.
echo ⏳ Waiting for services to start...
echo    MongoDB and Redis need some time to initialize
echo    GROBID may take 1-2 minutes to download models on first startup

REM Wait for service health checks
echo.
echo 🔍 Checking service status...
timeout /t 10 /nobreak >nul

REM Check API health status
set /a counter=0
:check_api
set /a counter+=1
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ API service is ready
    goto check_grobid
)
if %counter% geq 30 (
    echo ⚠️ API service startup timeout, please check logs
    goto check_grobid
)
echo ⏳ Waiting for API service to start... (%counter%/30)
timeout /t 5 /nobreak >nul
goto check_api

:check_grobid
set /a counter=0
:check_grobid_loop
set /a counter+=1
curl -s http://localhost:8070/api/isalive >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GROBID service is ready
    goto finished
)
if %counter% geq 30 (
    echo ⚠️ GROBID service startup timeout, please check logs
    goto finished
)
echo ⏳ Waiting for GROBID service to start... (%counter%/30)
timeout /t 5 /nobreak >nul
goto check_grobid_loop

:finished
echo.
echo 🚀 All services are running! You can now start using the literature parsing system
echo.
echo 📖 Quick test:
echo curl -X POST "http://localhost:8000/api/literature" ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"title\": \"Attention Is All You Need\", \"authors\": [\"Vaswani et al.\"]}"
echo.
echo Press any key to exit...
pause >nul 