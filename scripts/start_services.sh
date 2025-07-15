#!/bin/bash

# Literature Parser Backend - 一键启动脚本
# 该脚本会启动完整的文献解析生态系统

set -e

echo "🚀 Literature Parser Backend - 一键启动"
echo "========================================"

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 检查Docker Compose是否可用
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo "📝 创建 .env 配置文件..."
    cat > .env << EOF
# Literature Parser Backend Configuration
LITERATURE_PARSER_BACKEND_VERSION=latest
LITERATURE_PARSER_BACKEND_HOST=0.0.0.0
LITERATURE_PARSER_BACKEND_PORT=8000
LITERATURE_PARSER_BACKEND_LOG_LEVEL=INFO
LITERATURE_PARSER_BACKEND_RELOAD=False

# Database Configuration
LITERATURE_PARSER_BACKEND_DB_HOST=literature_parser_backend-db
LITERATURE_PARSER_BACKEND_DB_PORT=27017
LITERATURE_PARSER_BACKEND_DB_USER=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_PASS=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_BASE=admin

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# External Services
GROBID_URL=http://grobid:8070
CROSSREF_EMAIL=literature-parser@example.com

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=json
CELERY_TIMEZONE=UTC
CELERY_ENABLE_UTC=True
EOF
    echo "✅ .env 文件已创建"
fi

# 检查启动模式
MODE=${1:-production}

if [ "$MODE" = "dev" ] || [ "$MODE" = "development" ]; then
    echo "🔧 启动开发环境..."
    echo "包含服务: API, Worker, MongoDB, Redis, GROBID, Redis Commander, Mongo Express"
    
    # 启动开发环境
    docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build -d
    
    echo ""
    echo "🎉 开发环境启动完成！"
    echo ""
    echo "📋 服务地址:"
    echo "  • API 文档:        http://localhost:8000/docs"
    echo "  • API 健康检查:    http://localhost:8000/api/health"
    echo "  • Redis Commander: http://localhost:8081"
    echo "  • Mongo Express:   http://localhost:8082"
    echo "  • GROBID:          http://localhost:8070"
    echo ""
    echo "🔍 查看日志: docker-compose logs -f [service_name]"
    echo "🛑 停止服务: docker-compose down"
    
else
    echo "🏭 启动生产环境..."
    echo "包含服务: API, Worker, MongoDB, Redis, GROBID"
    
    # 启动生产环境
    docker-compose up --build -d
    
    echo ""
    echo "🎉 生产环境启动完成！"
    echo ""
    echo "📋 服务地址:"
    echo "  • API 文档:        http://localhost:8000/docs"
    echo "  • API 健康检查:    http://localhost:8000/api/health"
    echo ""
    echo "🔍 查看日志: docker-compose logs -f [service_name]"
    echo "🛑 停止服务: docker-compose down"
fi

echo ""
echo "⏳ 等待服务启动完成..."
echo "   MongoDB 和 Redis 需要一些时间初始化"
echo "   GROBID 首次启动可能需要 1-2 分钟下载模型"

# 等待服务健康检查
echo ""
echo "🔍 检查服务状态..."
sleep 10

# 检查API健康状态
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ API 服务已就绪"
        break
    fi
    echo "⏳ 等待 API 服务启动... ($i/30)"
    sleep 5
done

# 检查GROBID健康状态
for i in {1..30}; do
    if curl -s http://localhost:8070/api/isalive > /dev/null 2>&1; then
        echo "✅ GROBID 服务已就绪"
        break
    fi
    echo "⏳ 等待 GROBID 服务启动... ($i/30)"
    sleep 5
done

echo ""
echo "🚀 所有服务已启动！可以开始使用文献解析系统了"
echo ""
echo "📖 快速测试:"
echo "curl -X POST 'http://localhost:8000/api/literature' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"title\": \"Attention Is All You Need\", \"authors\": [\"Vaswani et al.\"]}'" 