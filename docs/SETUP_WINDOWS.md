# Windows 环境安装指南

## 🛠️ 环境准备

### 1. 安装 Docker Desktop

**下载地址**: https://www.docker.com/products/docker-desktop/

**安装步骤**:
1. 下载 Docker Desktop for Windows
2. 运行安装程序
3. 重启计算机
4. 启动 Docker Desktop
5. 等待 Docker 引擎启动完成

**验证安装**:
```powershell
docker --version
docker-compose --version
```

### 2. 配置 Docker Desktop

**推荐设置**:
- **内存**: 至少 4GB (推荐 8GB)
- **CPU**: 至少 2 核心
- **磁盘空间**: 至少 20GB 可用空间

**配置路径**: Docker Desktop → Settings → Resources

### 3. 启用 WSL2 (推荐)

如果您使用 WSL2，请确保：
1. Windows 10 版本 1903 或更高
2. 启用 WSL2 功能
3. Docker Desktop 设置中启用 WSL2 集成

## 🚀 快速启动

### 方法1: 使用批处理脚本

```batch
# 生产环境
start_services.bat

# 开发环境
start_services.bat dev
```

### 方法2: 手动启动

```powershell
# 生产环境
docker-compose up --build -d

# 开发环境
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up --build -d
```

## 🔧 常见问题解决

### 1. Docker 未启动

**错误**: `error during connect: This error may indicate that the docker daemon is not running`

**解决方案**:
1. 启动 Docker Desktop
2. 等待 Docker 引擎完全启动
3. 检查系统托盘中的 Docker 图标

### 2. 端口冲突

**错误**: `port is already allocated`

**解决方案**:
```powershell
# 查看端口占用
netstat -ano | findstr :8000

# 终止占用进程
taskkill /PID <PID> /F
```

### 3. 权限问题

**错误**: `permission denied`

**解决方案**:
1. 以管理员身份运行 PowerShell
2. 或者将当前用户添加到 docker-users 组

### 4. 网络问题

**错误**: `network not found`

**解决方案**:
```powershell
# 重置 Docker 网络
docker network prune
docker-compose down
docker-compose up --build -d
```

## 📋 服务验证

启动完成后，访问以下地址验证服务：

- **API 文档**: http://localhost:8000/docs
- **API 健康检查**: http://localhost:8000/api/health
- **GROBID 服务**: http://localhost:8070/api/isalive
- **Redis Commander**: http://localhost:8081 (仅开发环境)
- **Mongo Express**: http://localhost:8082 (仅开发环境)

## 🛠️ 开发工具

### PowerShell 脚本

```powershell
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f api

# 重启服务
docker-compose restart api

# 停止服务
docker-compose down
```

### 性能监控

```powershell
# 查看容器资源使用
docker stats

# 查看镜像大小
docker images

# 清理未使用的资源
docker system prune
```

## 🔄 更新和维护

### 更新代码

```powershell
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up --build -d
```

### 数据备份

```powershell
# 备份 MongoDB
docker-compose exec db mongodump --out /backup

# 备份 Redis
docker-compose exec redis redis-cli SAVE
```

## 🚨 故障排除

### 常用诊断命令

```powershell
# 检查 Docker 状态
docker info

# 检查容器日志
docker-compose logs --tail=50 api

# 检查网络连接
docker network ls

# 检查数据卷
docker volume ls
```

### 完全重置

如果遇到严重问题，可以完全重置：

```powershell
# 停止所有服务
docker-compose down -v

# 清理所有 Docker 资源
docker system prune -a --volumes

# 重新启动
start_services.bat
```

## 📞 技术支持

如果遇到问题：

1. 检查 Docker Desktop 是否正常运行
2. 查看容器日志: `docker-compose logs -f`
3. 检查端口占用: `netstat -ano | findstr :8000`
4. 验证网络连接: `docker network ls`
5. 重启 Docker Desktop

---

**🎉 恭喜！您的 Windows 环境已准备就绪！** 