# MongoDB to Neo4j 迁移完整指南

## 🎯 迁移概述

本指南将帮助您将文献解析后端从 MongoDB 迁移到 Neo4j，以支持更强大的图关系查询能力。迁移采用分阶段的方式，确保系统稳定性。

### 迁移阶段

```
Phase 1: 基础功能替换 (功能对等)
├── 基础设施搭建 ✅
├── 数据模型映射 ✅ 
├── DAO层重构 ✅
├── 数据迁移脚本 ✅
└── API功能验证 🔄

Phase 2: 图能力激活 (增强功能)
├── 悬空引用解析 ⏳
├── 图关系构建 ⏳
└── 新API开发 ⏳
```

## 📋 前置条件

### 系统要求
- Docker & Docker Compose
- Python 3.11+
- 足够的磁盘空间 (推荐至少 10GB)
- 内存推荐 8GB+ (Neo4j 需要较多内存)

### 依赖检查
```bash
# 检查Docker版本
sudo docker --version
sudo docker compose version

# 检查Python版本  
python3 --version

# 安装Python依赖
poetry install  # 如果使用Poetry
# 或者 pip install neo4j elasticsearch

# 检查可用磁盘空间
df -h
```

## 🚀 快速开始

### 一键启动迁移

```bash
# 1. 克隆并进入项目目录
cd /path/to/your/project

# 2. 给脚本执行权限
chmod +x scripts/start_migration.sh

# 3. 启动迁移向导
./scripts/start_migration.sh
```

该脚本会自动：
- 检查环境配置
- 启动所需服务
- 提供迁移选项
- 引导完成迁移

## 📖 详细步骤指南

### Step 1: 环境配置

#### 1.1 创建 Neo4j 配置

项目包含了预配置的 `docker-compose.neo4j.yml`，支持：
- Neo4j Community Edition 5.15
- Elasticsearch 8.11.0  
- 原有 MongoDB（双数据库并存）

#### 1.2 环境变量设置

在 `.env` 文件中添加：

```env
# 数据库操作模式
LITERATURE_PARSER_BACKEND_DB_MODE=dual  # mongodb_only | dual | neo4j_only

# Neo4j 配置
LITERATURE_PARSER_BACKEND_NEO4J_URI=bolt://localhost:7687
LITERATURE_PARSER_BACKEND_NEO4J_USERNAME=neo4j
LITERATURE_PARSER_BACKEND_NEO4J_PASSWORD=literature_parser_neo4j

# Elasticsearch 配置
LITERATURE_PARSER_BACKEND_ES_HOST=localhost
LITERATURE_PARSER_BACKEND_ES_PORT=9200
LITERATURE_PARSER_BACKEND_ES_USERNAME=elastic
LITERATURE_PARSER_BACKEND_ES_PASSWORD=literature_parser_elastic
```

### Step 2: 启动服务

```bash
# 启动所有服务 (MongoDB + Neo4j + Elasticsearch)
docker-compose -f docker-compose.neo4j.yml up -d

# 查看服务状态
docker-compose -f docker-compose.neo4j.yml ps

# 检查服务健康状态
docker-compose -f docker-compose.neo4j.yml logs -f neo4j
docker-compose -f docker-compose.neo4j.yml logs -f elasticsearch
```

### Step 3: 数据迁移

#### 3.1 迁移前准备 (推荐)

```bash
# 1. 干运行分析
python scripts/mongodb_to_neo4j_migration.py --dry-run

# 2. 备份现有数据
mongodump --host localhost:27017 --db literature_parser --out backup/
```

#### 3.2 执行迁移

```bash
# 选项1: 完整迁移
python scripts/mongodb_to_neo4j_migration.py --batch-size 100

# 选项2: 恢复中断的迁移  
python scripts/mongodb_to_neo4j_migration.py --resume "2017-vaswani-aiaynu-a8c4"

# 选项3: 小批量测试
python scripts/mongodb_to_neo4j_migration.py --batch-size 10
```

#### 3.3 验证迁移结果

```bash
# 运行功能测试
python scripts/test_migration_functionality.py

# 检查数据一致性
python -c "
import asyncio
from literature_parser_backend.db.database_manager import DatabaseManager
from literature_parser_backend.settings import Settings

async def check():
    db = DatabaseManager(Settings())
    await db.initialize()
    
    # 获取统计信息
    if hasattr(db, '_mongodb_dao'):
        mongo_count = await db._mongodb_dao.get_literature_count()
        print(f'MongoDB: {mongo_count} literatures')
    
    if hasattr(db, '_neo4j_dao'):
        neo4j_count = await db._neo4j_dao.get_literature_count()
        print(f'Neo4j: {neo4j_count} literatures')

asyncio.run(check())
"
```

## 🔧 数据库模式说明

### MongoDB Only (mongodb_only)
- 只使用 MongoDB
- 现状保持，无新功能

### Dual Mode (dual) - 推荐迁移期间使用
- 同时使用 MongoDB 和 Neo4j
- 写入操作同时写入两个数据库
- 读取操作优先使用 Neo4j，回退到 MongoDB
- 适合迁移过渡期

### Neo4j Only (neo4j_only) - 最终目标
- 只使用 Neo4j
- 完整的图数据库功能
- 最佳性能和新特性

### 模式切换

```bash
# 修改 .env 文件
LITERATURE_PARSER_BACKEND_DB_MODE=neo4j_only

# 重启服务
docker-compose -f docker-compose.neo4j.yml restart api worker
```

## 🖥️ 管理界面和工具

### Neo4j Browser
- URL: http://localhost:7474
- 用户名: neo4j  
- 密码: literature_parser_neo4j

#### 常用查询
```cypher
// 查看数据概览
MATCH (n) RETURN labels(n) as label, count(n) as count

// 查看文献节点
MATCH (lit:Literature) RETURN lit LIMIT 10

// 查看别名映射
MATCH (alias:Alias)-[:IDENTIFIES]->(lit:Literature) 
RETURN alias, lit LIMIT 10

// 统计引用关系 (Phase 2 后可用)
MATCH ()-[r:CITES]->() RETURN count(r) as citation_count
```

### Elasticsearch
- URL: http://localhost:9200
- 用户名: elastic
- 密码: literature_parser_elastic

## 🐛 故障排除

### 常见问题

#### 1. Neo4j 启动失败
```bash
# 检查日志
docker-compose -f docker-compose.neo4j.yml logs neo4j

# 常见原因：内存不足
# 解决方案：在 docker-compose.neo4j.yml 中调整内存设置
```

#### 2. Elasticsearch 内存错误
```bash
# 检查系统内存
free -h

# 调整 vm.max_map_count (Linux)
sudo sysctl -w vm.max_map_count=262144
```

#### 3. 迁移中断
```bash
# 查看迁移日志
ls -la migration_*.log

# 从中断处恢复
python scripts/mongodb_to_neo4j_migration.py --resume "last_successful_lid"
```

#### 4. 数据不一致
```bash
# 重新运行迁移
python scripts/mongodb_to_neo4j_migration.py --dry-run

# 如果严重不一致，清空 Neo4j 重新迁移
docker-compose -f docker-compose.neo4j.yml exec neo4j cypher-shell -u neo4j -p literature_parser_neo4j "MATCH (n) DETACH DELETE n"
```

### 性能优化

#### Neo4j 性能调优
```bash
# 编辑 docker-compose.neo4j.yml 中的 Neo4j 配置
environment:
  - NEO4J_dbms_memory_heap_initial__size=1g
  - NEO4J_dbms_memory_heap_max__size=4g
  - NEO4J_dbms_memory_pagecache_size=2g
```

#### 迁移性能优化
```bash
# 增加批处理大小
python scripts/mongodb_to_neo4j_migration.py --batch-size 500

# 并行处理 (自定义实现)
# 将数据按 LID 范围分割，多进程迁移
```

## 📊 监控和日志

### 日志文件
- 迁移日志: `migration_YYYYMMDD_HHMMSS.log`
- 测试结果: `migration_test_results.json`
- Docker 日志: `docker-compose -f docker-compose.neo4j.yml logs`

### 监控指标
```bash
# 数据库连接状态
curl -f http://localhost:8000/api/monitoring/health

# Neo4j 度量
curl -u neo4j:literature_parser_neo4j http://localhost:7474/db/data/

# Elasticsearch 状态
curl -u elastic:literature_parser_elastic http://localhost:9200/_cluster/health
```

## 🔄 回滚计划

如果需要回滚到纯 MongoDB 模式：

```bash
# 1. 停止服务
docker-compose -f docker-compose.neo4j.yml down

# 2. 修改环境变量
# 在 .env 中设置：LITERATURE_PARSER_BACKEND_DB_MODE=mongodb_only

# 3. 启动原始服务
docker-compose up -d

# 4. 验证功能正常
curl http://localhost:8000/api/monitoring/health
```

## 🎯 Phase 2: 图能力激活 (后续)

Phase 1 完成后，您可以继续 Phase 2 的开发：

### 主要功能
- 悬空引用自动解析
- 真实引用关系构建  
- N度引用网络查询
- 引用路径发现
- 文献影响力分析

### API 端点扩展
- `GET /api/literatures/{lid}/citations?depth=2` - 引用网络
- `GET /api/literatures/{lid}/cited_by` - 被引列表
- `GET /api/path/{lid1}/{lid2}` - 引用路径
- `GET /api/graphs?lids=lid1,lid2` - 关系图谱

## 📞 支持和贡献

### 获取帮助
- 查看日志文件定位问题
- 运行测试脚本验证功能
- 检查 GitHub Issues

### 贡献改进
- 报告迁移过程中遇到的问题
- 提交性能优化建议
- 分享最佳实践

---

**🎉 恭喜！您已完成 MongoDB 到 Neo4j 的迁移。现在可以享受强大的图数据库功能了！**
