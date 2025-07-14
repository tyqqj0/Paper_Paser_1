# Literature Parser Backend - Docker 部署指南

## 🏗️ 架构概述

本系统采用微服务架构，包含以下核心服务：

```
┌─────────────────────────────────────────────────────────────┐
│                    Literature Parser Backend                │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │   API   │  │ Worker  │  │ MongoDB │  │  Redis  │        │
│  │ FastAPI │  │ Celery  │  │Database │  │ Broker  │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│  │ GROBID  │  │Redis-UI │  │Mongo-UI │                     │
│  │PDF解析  │  │(可选)   │  │(可选)   │                     │
│  └─────────┘  └─────────┘  └─────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速启动

### 方式1：一键启动脚本（推荐）

**Linux/macOS:**
```bash
# 生产环境
./start_services.sh

# 开发环境（包含管理界面）
./start_services.sh dev
```

**Windows:**
```batch
# 生产环境
start_services.bat

# 开发环境（包含管理界面）
start_services.bat dev
```

### 方式2：手动启动

**生产环境:**
```bash
docker-compose up --build -d
```

**开发环境:**
```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build -d
```

## 📋 服务详情

### 核心服务

| 服务名称   | 端口  | 描述                 | 健康检查                            |
| ---------- | ----- | -------------------- | ----------------------------------- |
| **api**    | 8000  | FastAPI 应用服务     | `http://localhost:8000/api/health`  |
| **worker** | -     | Celery 后台任务处理  | 通过日志检查                        |
| **db**     | 27017 | MongoDB 数据库       | 内置健康检查                        |
| **redis**  | 6379  | Redis 缓存和消息队列 | 内置健康检查                        |
| **grobid** | 8070  | GROBID PDF解析服务   | `http://localhost:8070/api/isalive` |

### 开发工具（仅开发环境）

| 服务名称            | 端口 | 描述             | 访问地址                |
| ------------------- | ---- | ---------------- | ----------------------- |
| **redis-commander** | 8081 | Redis 管理界面   | `http://localhost:8081` |
| **mongo-express**   | 8082 | MongoDB 管理界面 | `http://localhost:8082` |

## 🔧 配置说明

### 环境变量配置

系统通过 `.env` 文件进行配置。启动脚本会自动创建默认配置：

```env
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
```

### 服务依赖关系

```yaml
api:
  depends_on:
    - db (健康检查)
    - redis (健康检查)

worker:
  depends_on:
    - db (健康检查)
    - redis (健康检查)
    - grobid (启动完成)

redis-commander:
  depends_on:
    - redis (健康检查)

mongo-express:
  depends_on:
    - db (健康检查)
```

## 🛠️ 运维操作

### 常用命令

```bash
# 查看所有服务状态
docker-compose ps

# 查看服务日志
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f db
docker-compose logs -f redis
docker-compose logs -f grobid

# 重启特定服务
docker-compose restart api
docker-compose restart worker

# 停止所有服务
docker-compose down

# 停止并删除数据卷（谨慎使用）
docker-compose down -v

# 重新构建镜像
docker-compose build --no-cache

# 查看资源使用情况
docker stats
```

### 健康检查

```bash
# API 健康检查
curl http://localhost:8000/api/health

# GROBID 健康检查
curl http://localhost:8070/api/isalive

# Redis 健康检查
docker-compose exec redis redis-cli ping

# MongoDB 健康检查
docker-compose exec db mongosh --eval "db.runCommand('ping')"
```

## 📊 监控和调试

### 日志管理

```bash
# 实时查看所有日志
docker-compose logs -f

# 查看特定服务的最近日志
docker-compose logs --tail=100 api

# 查看错误日志
docker-compose logs | grep ERROR

# 导出日志到文件
docker-compose logs > system.log 2>&1
```

### 性能监控

```bash
# 查看容器资源使用
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# 查看数据卷使用情况
docker volume ls
docker system df
```

### 调试模式

开发环境自动启用调试功能：

- **API热重载**: 代码变更自动重启
- **详细日志**: DEBUG级别日志输出
- **管理界面**: Redis Commander + Mongo Express
- **Volume挂载**: 本地代码直接挂载到容器

## 🔒 安全配置

### 生产环境建议

1. **修改默认密码**:
   ```env
   LITERATURE_PARSER_BACKEND_DB_USER=your_secure_username
   LITERATURE_PARSER_BACKEND_DB_PASS=your_secure_password
   ```

2. **限制端口暴露**:
   ```yaml
   # 仅暴露必要端口
   ports:
     - "127.0.0.1:8000:8000"  # 仅本地访问
   ```

3. **使用HTTPS**:
   ```yaml
   # 添加反向代理（如Nginx）
   nginx:
     image: nginx:alpine
     ports:
       - "443:443"
     volumes:
       - ./nginx.conf:/etc/nginx/nginx.conf
       - ./ssl:/etc/nginx/ssl
   ```

4. **网络隔离**:
   ```yaml
   # 使用自定义网络
   networks:
     literature_parser_network:
       driver: bridge
       ipam:
         config:
           - subnet: 172.20.0.0/16
   ```

## 🚨 故障排除

### 常见问题

1. **端口冲突**:
   ```bash
   # 检查端口占用
   netstat -tulpn | grep :8000
   
   # 修改端口映射
   ports:
     - "8001:8000"  # 使用不同的外部端口
   ```

2. **内存不足**:
   ```bash
   # 增加Docker内存限制
   docker-compose up --memory=4g
   
   # 或在docker-compose.yml中设置
   deploy:
     resources:
       limits:
         memory: 2G
   ```

3. **GROBID启动慢**:
   ```bash
   # 首次启动需要下载模型，耐心等待
   docker-compose logs -f grobid
   
   # 预热GROBID
   curl -X POST http://localhost:8070/api/processHeaderDocument \
     -F "input=@sample.pdf"
   ```

4. **数据库连接失败**:
   ```bash
   # 检查MongoDB状态
   docker-compose exec db mongosh --eval "db.runCommand('ping')"
   
   # 重启数据库
   docker-compose restart db
   ```

### 日志分析

```bash
# 查找错误模式
docker-compose logs | grep -i error
docker-compose logs | grep -i exception
docker-compose logs | grep -i failed

# 分析API响应时间
docker-compose logs api | grep "INFO.*GET\|POST\|PUT\|DELETE"

# 监控任务执行情况
docker-compose logs worker | grep "Task\|Celery"
```

## 📈 性能优化

### 资源配置

```yaml
# 优化Celery Worker
worker:
  command: poetry run celery -A literature_parser_backend.worker.celery_app worker --loglevel=info --concurrency=4 --prefetch-multiplier=1
  deploy:
    resources:
      limits:
        memory: 2G
        cpus: '2'

# 优化GROBID
grobid:
  environment:
    JAVA_OPTS: "-Xmx4g -XX:+UseG1GC"
  deploy:
    resources:
      limits:
        memory: 4G
        cpus: '2'
```

### 缓存策略

```yaml
# Redis持久化配置
redis:
  command: redis-server --appendonly yes --appendfsync everysec
  volumes:
    - redis-data:/data
```

## 🔄 备份和恢复

### 数据备份

```bash
# MongoDB备份
docker-compose exec db mongodump --out /backup
docker cp $(docker-compose ps -q db):/backup ./mongodb_backup

# Redis备份
docker-compose exec redis redis-cli SAVE
docker cp $(docker-compose ps -q redis):/data/dump.rdb ./redis_backup
```

### 数据恢复

```bash
# MongoDB恢复
docker cp ./mongodb_backup $(docker-compose ps -q db):/backup
docker-compose exec db mongorestore /backup

# Redis恢复
docker cp ./redis_backup/dump.rdb $(docker-compose ps -q redis):/data/
docker-compose restart redis
```

## 🚀 部署到生产环境

### 1. 服务器准备

```bash
# 安装Docker和Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# 安装Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### 2. 环境配置

```bash
# 创建生产环境配置
cp .env.example .env.production
# 编辑生产环境配置
vi .env.production
```

### 3. 启动服务

```bash
# 使用生产环境配置
docker-compose --env-file .env.production up -d --build

# 验证服务状态
docker-compose ps
curl http://localhost:8000/api/health
```

### 4. 反向代理配置

```nginx
# nginx.conf
upstream literature_parser_api {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://literature_parser_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 📞 技术支持

如果遇到问题，请按以下步骤排查：

1. **检查服务状态**: `docker-compose ps`
2. **查看日志**: `docker-compose logs -f [service_name]`
3. **验证健康检查**: 访问健康检查端点
4. **检查网络连接**: `docker network ls`
5. **验证数据卷**: `docker volume ls`

更多问题请查看项目文档或提交Issue。

**🎉 恭喜！您的Literature Parser Backend已成功部署！** 