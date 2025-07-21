@echo off
echo 🔍 检查Docker容器日志
echo =====================================

echo.
echo 📊 检查所有容器状态:
docker-compose ps

@REM echo.
@REM echo 🔧 API容器日志 (最后50行):
@REM echo -------------------------------------
@REM docker-compose logs --tail=50 api

echo.
echo 👷 Worker容器日志 (最后50行):
echo -------------------------------------
docker-compose logs --tail=50 worker

@REM echo.
@REM echo 📦 Redis容器日志 (最后20行):
@REM echo -------------------------------------
@REM docker-compose logs --tail=20 redis

@REM echo.
@REM echo 🗄️ MongoDB容器日志 (最后20行):
@REM echo -------------------------------------
@REM docker-compose logs --tail=20 db

echo.
echo 🌐 GROBID容器日志 (最后20行):
echo -------------------------------------
docker-compose logs --tail=50 grobid

echo.
echo =====================================
echo 🔍 日志检查完成
pause