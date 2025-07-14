@echo off
setlocal enabledelayedexpansion

REM Literature Parser Backend - Windows一键启动脚本
REM 该脚本会启动完整的文献解析生态系统

echo.
echo 🚀 Literature Parser Backend - 一键启动
echo ========================================

REM 检查Docker是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

REM 检查Docker Compose是否可用
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ docker-compose 未安装，请先安装 Docker Compose
    pause
    exit /b 1
)

REM 创建 .env 文件（如果不存在）
if not exist .env (
    echo 📝 创建 .env 配置文件...
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
    echo ✅ .env 文件已创建
)

REM 检查启动模式
set MODE=%1
if "%MODE%"=="" set MODE=production

if "%MODE%"=="dev" (
    set MODE=development
)

if "%MODE%"=="development" (
    echo 🔧 启动开发环境...
    echo 包含服务: API, Worker, MongoDB, Redis, GROBID, Redis Commander, Mongo Express
    
    REM 启动开发环境
    docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build -d
    
    echo.
    echo 🎉 开发环境启动完成！
    echo.
    echo 📋 服务地址:
    echo   • API 文档:        http://localhost:8000/docs
    echo   • API 健康检查:    http://localhost:8000/api/health
    echo   • Redis Commander: http://localhost:8081
    echo   • Mongo Express:   http://localhost:8082
    echo   • GROBID:          http://localhost:8070
    echo.
    echo 🔍 查看日志: docker-compose logs -f [service_name]
    echo 🛑 停止服务: docker-compose down
    
) else (
    echo 🏭 启动生产环境...
    echo 包含服务: API, Worker, MongoDB, Redis, GROBID
    
    REM 启动生产环境
    docker-compose up --build -d
    
    echo.
    echo 🎉 生产环境启动完成！
    echo.
    echo 📋 服务地址:
    echo   • API 文档:        http://localhost:8000/docs
    echo   • API 健康检查:    http://localhost:8000/api/health
    echo.
    echo 🔍 查看日志: docker-compose logs -f [service_name]
    echo 🛑 停止服务: docker-compose down
)

echo.
echo ⏳ 等待服务启动完成...
echo    MongoDB 和 Redis 需要一些时间初始化
echo    GROBID 首次启动可能需要 1-2 分钟下载模型

REM 等待服务健康检查
echo.
echo 🔍 检查服务状态...
timeout /t 10 /nobreak >nul

REM 检查API健康状态
set /a counter=0
:check_api
set /a counter+=1
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ API 服务已就绪
    goto check_grobid
)
if %counter% geq 30 (
    echo ⚠️ API 服务启动超时，请检查日志
    goto check_grobid
)
echo ⏳ 等待 API 服务启动... (%counter%/30)
timeout /t 5 /nobreak >nul
goto check_api

:check_grobid
set /a counter=0
:check_grobid_loop
set /a counter+=1
curl -s http://localhost:8070/api/isalive >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ GROBID 服务已就绪
    goto finished
)
if %counter% geq 30 (
    echo ⚠️ GROBID 服务启动超时，请检查日志
    goto finished
)
echo ⏳ 等待 GROBID 服务启动... (%counter%/30)
timeout /t 5 /nobreak >nul
goto check_grobid_loop

:finished
echo.
echo 🚀 所有服务已启动！可以开始使用文献解析系统了
echo.
echo 📖 快速测试:
echo curl -X POST "http://localhost:8000/api/literature" ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"title\": \"Attention Is All You Need\", \"authors\": [\"Vaswani et al.\"]}"
echo.
echo 按任意键退出...
pause >nul 