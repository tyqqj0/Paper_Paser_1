# 🚀 Literature Parser Backend - 设置说明

## 📋 快速开始

### 1. 创建环境变量文件

```bash
# 复制环境变量模板
cp env.example .env
```

### 2. 启动所有服务

```bash
# 停止现有服务
docker-compose down

# 启动服务（重新构建）
docker-compose up --build -d
```

### 3. 验证服务状态

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api
docker-compose logs -f worker
```

### 4. 测试 API

```bash
# 健康检查
curl http://localhost:8000/api/health

# 提交测试任务
python test_real_url.py
```

## 🔧 环境变量配置

### 关键配置说明

| 变量名                                        | 值                          | 说明            |
| --------------------------------------------- | --------------------------- | --------------- |
| `LITERATURE_PARSER_BACKEND_DB_HOST`           | `db`                        | MongoDB 服务名  |
| `LITERATURE_PARSER_BACKEND_DB_BASE`           | `admin`                     | 认证数据库      |
| `LITERATURE_PARSER_BACKEND_DB_USER`           | `literature_parser_backend` | 数据库用户名    |
| `LITERATURE_PARSER_BACKEND_DB_PASS`           | `literature_parser_backend` | 数据库密码      |
| `LITERATURE_PARSER_BACKEND_REDIS_HOST`        | `redis`                     | Redis 服务名    |
| `LITERATURE_PARSER_BACKEND_CELERY_BROKER_URL` | `redis://redis:6379/0`      | Celery 消息队列 |

### 完整的 .env 文件内容

```env
# App configuration
LITERATURE_PARSER_BACKEND_HOST=0.0.0.0
LITERATURE_PARSER_BACKEND_PORT=8000
LITERATURE_PARSER_BACKEND_WORKERS_COUNT=1
LITERATURE_PARSER_BACKEND_LOG_LEVEL=INFO

# Database configuration
LITERATURE_PARSER_BACKEND_DB_HOST=db
LITERATURE_PARSER_BACKEND_DB_PORT=27017
LITERATURE_PARSER_BACKEND_DB_USER=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_PASS=literature_parser_backend
LITERATURE_PARSER_BACKEND_DB_BASE=admin

# Redis configuration
LITERATURE_PARSER_BACKEND_REDIS_HOST=redis
LITERATURE_PARSER_BACKEND_REDIS_PORT=6379
LITERATURE_PARSER_BACKEND_REDIS_DB=0
LITERATURE_PARSER_BACKEND_REDIS_PASSWORD=

# External services
LITERATURE_PARSER_BACKEND_GROBID_BASE_URL=http://grobid:8070
LITERATURE_PARSER_BACKEND_CROSSREF_MAILTO=literature-parser@example.com

# Celery configuration
LITERATURE_PARSER_BACKEND_CELERY_BROKER_URL=redis://redis:6379/0
LITERATURE_PARSER_BACKEND_CELERY_RESULT_BACKEND=redis://redis:6379/0
```

## 🛠️ 故障排除

### 常见问题

#### 1. MongoDB 认证失败

**错误信息**: `Authentication failed`

**解决方案**:
- 确保 `LITERATURE_PARSER_BACKEND_DB_BASE=admin`
- 确保用户名密码正确
- 重启数据库服务: `docker-compose restart db`

#### 2. Celery Worker 无法连接 Redis

**错误信息**: `Connection refused`

**解决方案**:
- 检查 Redis 服务状态: `docker-compose ps redis`
- 确保环境变量使用服务名: `LITERATURE_PARSER_BACKEND_REDIS_HOST=redis`
- 重启 worker: `docker-compose restart worker`

#### 3. 任务一直处于 pending 状态

**可能原因**:
- Worker 没有正确启动
- 环境变量配置错误
- Redis 连接问题

**解决方案**:
```bash
# 查看 worker 日志
docker-compose logs -f worker

# 重启 worker
docker-compose restart worker

# 测试环境变量
python test_env_config.py
```

### 调试命令

```bash
# 查看所有服务状态
docker-compose ps

# 查看特定服务日志
docker-compose logs -f api
docker-compose logs -f worker  
docker-compose logs -f db
docker-compose logs -f redis

# 进入容器调试
docker-compose exec api bash
docker-compose exec worker bash

# 重启单个服务
docker-compose restart api
docker-compose restart worker

# 完全重新构建
docker-compose down
docker-compose up --build -d
```

## 📊 服务端口

| 服务            | 端口  | 用途                        |
| --------------- | ----- | --------------------------- |
| API             | 8000  | FastAPI 应用                |
| MongoDB         | 27017 | 数据库                      |
| Redis           | 6379  | 缓存和消息队列              |
| GROBID          | 8070  | PDF 解析服务                |
| Redis Commander | 8081  | Redis 管理界面 (开发模式)   |
| Mongo Express   | 8082  | MongoDB 管理界面 (开发模式) |

## 🧪 测试脚本

### 在 Docker 容器内运行测试（推荐）

```bash
# Windows
test_in_docker.bat

# Linux/Mac
./test_in_docker.sh
```

### 手动在容器内运行单个测试

```bash
# 检查所有服务状态
docker-compose exec api python check_services.py

# 测试环境变量配置
docker-compose exec api python test_env_config.py

# 测试 API 健康检查
docker-compose exec api python quick_test.py

# 测试完整流程
docker-compose exec api python test_real_url.py

# 测试 Celery 连接
docker-compose exec api python test_celery_simple.py
```

### 在宿主机运行测试（不推荐）

⚠️ **注意**: 在宿主机运行测试可能会因为网络和环境变量配置不同而失败。推荐使用容器内测试。

```bash
# 如果一定要在宿主机测试，需要先设置环境变量
export LITERATURE_PARSER_BACKEND_DB_HOST=localhost
export LITERATURE_PARSER_BACKEND_REDIS_HOST=localhost
# ... 其他环境变量

python test_env_config.py
python quick_test.py
python test_real_url.py
python test_celery_simple.py
```

## 📝 开发模式

启动开发模式（包含管理界面）:

```bash
# Windows
start_services.bat dev

# Linux/Mac
./start_services.sh dev
```

开发模式额外服务:
- Redis Commander: http://localhost:8081
- Mongo Express: http://localhost:8082

## 🎯 验证清单

启动后请验证以下项目:

- [ ] 所有服务都在运行: `docker-compose ps`
- [ ] 服务健康检查通过: `docker-compose exec api python check_services.py`
- [ ] 可以访问 API 文档: http://localhost:8000/docs
- [ ] Worker 日志显示正常: `docker-compose logs worker`
- [ ] 运行完整测试套件: `test_in_docker.bat` (Windows) 或 `./test_in_docker.sh` (Linux/Mac)

### 快速验证命令

```bash
# Windows
test_in_docker.bat

# Linux/Mac  
./test_in_docker.sh

# 或者只检查服务状态
docker-compose exec api python check_services.py
```

如果以上所有项目都通过，说明系统配置正确！ 