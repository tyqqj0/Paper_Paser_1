#!/bin/bash

echo "🧪 在 Docker 容器内运行测试"
echo "==============================="

echo
echo "📋 0. 检查服务状态..."
docker-compose exec api python check_services.py

echo
echo "📋 1. 测试环境变量配置..."
docker-compose exec api python test_env_config.py

echo
echo "📋 2. 测试 API 健康检查..."
docker-compose exec api python quick_test.py

echo
echo "📋 3. 测试完整流程 (ArXiv URL)..."
docker-compose exec api python test_real_url.py

echo
echo "📋 4. 测试 Celery 连接..."
docker-compose exec api python test_celery_simple.py

echo
echo "✅ 所有测试完成！" 