# Celery 异步任务系统集成

本文档说明了文献解析系统中 Celery 异步任务处理的设计和使用方法。

## 🏗️ 架构概述

我们的 Celery 集成采用了现代 Python 异步编程模式，将耗时的文献处理任务从 Web API 中分离出来，确保系统的响应性和可扩展性。

### 核心组件

```
literature_parser_backend/worker/
├── __init__.py          # Worker 包导出
├── celery_app.py       # Celery 应用配置
├── tasks.py            # 核心文献处理任务
├── worker.py           # Worker 启动脚本
└── test_tasks.py       # 任务测试套件
```

## ⚙️ 技术实现

### 1. Celery 应用配置 (`celery_app.py`)

**核心特性**:
- **Redis 作为 Broker**: 高性能消息队列
- **任务路由**: 专用的 `literature` 队列
- **结果持久化**: 任务结果保存 1 小时
- **超时控制**: 硬超时 30 分钟，软超时 25 分钟

**配置要点**:
```python
# 从 settings.py 读取配置
celery_app = Celery(
    "literature_parser_worker",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
)

# 专业化配置
task_routes = {"literature_parser_worker.tasks.*": {"queue": "literature"}}
worker_prefetch_multiplier = 1  # 一次只处理一个任务
```

### 2. 智能混合文献处理任务 (`tasks.py`)

#### 🧠 核心算法: `process_literature_task`

这是系统的核心引擎，实现了完整的智能混合工作流：

**输入**: 文献源信息字典
```python
{
    "url": "https://doi.org/10.1038/nature12373",
    "title": "Optional fallback title",
    "authors": "Optional author info",
    "doi": "Direct DOI if available"
}
```

**输出**: MongoDB 中新创建的文献 ID (字符串)

#### 🔄 处理流程详解

##### 1. **权威标识符提取** (`extract_authoritative_identifiers`)
- **优先级**: DOI > ArXiv ID > 内容指纹
- **智能解析**: 从 URL 中提取 DOI 和 ArXiv ID
- **指纹生成**: 使用标题+作者+年份的 MD5 哈希

```python
# DOI 提取示例
url = "https://doi.org/10.1038/nature12373"
# 提取结果: DOI = "10.1038/nature12373"

# 指纹生成示例  
title = "Attention Is All You Need"
authors = "Vaswani et al."
year = "2017"
# 生成指纹: d7729da1a7b25d6f
```

##### 2. **元数据获取瀑布流** (`fetch_metadata_waterfall`)
- **主路径**: CrossRef API (权威性最高)
- **备用路径**: Semantic Scholar API (AI 增强)
- **最后备用**: GROBID PDF 解析

##### 3. **参考文献获取瀑布流** (`fetch_references_waterfall`)
- **主路径**: Semantic Scholar API (结构化最好)
- **备用路径**: GROBID PDF 解析

##### 4. **数据整合与持久化**
- **MongoDB 存储**: 使用 Motor 异步驱动
- **事务安全**: 错误时提供回退机制
- **任务状态**: 实时更新处理进度

#### 📊 任务状态管理

任务支持细粒度的状态跟踪：

```python
meta = {
    "stage": "正在获取元数据",
    "progress": 30,
    "details": "使用doi标识符",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

**状态阶段**:
- 正在初始化任务 (5%)
- 正在提取权威标识符 (10%)
- 正在获取元数据 (30%)
- 正在解析PDF元数据 (40%) - 仅在需要时
- 正在获取参考文献 (60%)
- 正在解析PDF参考文献 (70%) - 仅在需要时
- 正在整合数据 (80%)
- 正在保存到数据库 (90%)
- 任务完成 (100%)

### 3. 异步/同步适配

由于 Celery 任务必须是同步的，但我们的外部 API 客户端是异步的，我们使用了一个巧妙的适配模式：

```python
# 异步核心逻辑
async def _process_literature_async(task_id: str, source: Dict[str, Any]) -> str:
    # 所有异步操作在这里

# Celery 任务包装器
@celery_app.task(bind=True)
def process_literature_task(self, source: Dict[str, Any]) -> str:
    return asyncio.run(_process_literature_async(self.request.id, source))
```

## 🗄️ 数据库集成

### MongoDB 连接管理

**异步连接**: 使用 Motor 进行异步 MongoDB 操作
```python
# 数据库连接
await connect_to_mongodb(settings)

# 数据存储
literature_dao = LiteratureDAO()
literature_id = await literature_dao.create_literature(literature)
```

**索引优化**: 自动创建性能索引
- DOI 字段索引 (唯一查找)
- ArXiv ID 索引
- 全文搜索索引 (标题+作者)
- 创建时间索引 (排序)

### 数据模型兼容性

任务完全兼容我们定义的 Pydantic 模型：
- `LiteratureModel`: 完整的 MongoDB 文档
- `IdentifiersModel`: 权威标识符
- `MetadataModel`: 文献元数据
- `ContentModel`: 内容信息
- `ReferenceModel`: 参考文献

## 🚀 使用方法

### 1. 环境设置

**Redis 配置** (settings.py):
```python
# Redis 设置
redis_host: str = "localhost"
redis_port: int = 6379
redis_db: int = 0

# Celery 设置  
celery_task_time_limit: int = 30 * 60  # 30 分钟
celery_worker_prefetch_multiplier: int = 1
```

**环境变量支持**:
```bash
export LITERATURE_PARSER_BACKEND_REDIS_HOST="redis-server"
export LITERATURE_PARSER_BACKEND_REDIS_PORT="6379"
export LITERATURE_PARSER_BACKEND_CELERY_TASK_TIME_LIMIT="1800"
```

### 2. 启动 Worker

#### 方法一: 使用便捷脚本
```bash
python start_worker.py
```

#### 方法二: 使用 Celery 命令
```bash
celery -A literature_parser_backend.worker.celery_app worker \
    --loglevel=info \
    --concurrency=1 \
    --queues=literature \
    --hostname=literature-worker@%h
```

#### 方法三: 使用内置脚本
```bash
python -m literature_parser_backend.worker.worker
```

### 3. 提交任务

```python
from literature_parser_backend.worker import process_literature_task

# 创建任务
source_data = {
    "url": "https://doi.org/10.1038/nature12373",
    "title": "Sample Paper Title"
}

# 异步提交
task = process_literature_task.delay(source_data)
print(f"Task ID: {task.id}")

# 检查状态
result = task.get(timeout=1800)  # 30 分钟超时
print(f"Literature ID: {result}")
```

### 4. 监控任务状态

```python
from celery.result import AsyncResult
from literature_parser_backend.worker.celery_app import celery_app

# 通过任务 ID 获取状态
task_result = AsyncResult(task_id, app=celery_app)

if task_result.state == "PROCESSING":
    meta = task_result.info
    print(f"Stage: {meta['stage']}")
    print(f"Progress: {meta['progress']}%")
    print(f"Details: {meta['details']}")
elif task_result.state == "SUCCESS":
    literature_id = task_result.result
    print(f"Completed! Literature ID: {literature_id}")
elif task_result.state == "FAILURE":
    print(f"Failed: {task_result.info}")
```

## 🧪 测试

### 运行测试套件

```bash
# 运行完整测试
python -m literature_parser_backend.worker.test_tasks

# 测试覆盖
✓ 权威标识符提取 (DOI, ArXiv, 指纹)
✓ 输入数据验证 
✓ Celery 任务注册
✓ 文献处理流水线 (模拟)
✓ 数据库保存 (模拟)
```

### 测试输出示例

```
============================================================
RUNNING CELERY TASK TESTS
============================================================
Testing identifier extraction...
✓ Correct primary type: doi
✓ Correct DOI: 10.1038/nature12373
✓ Correct ArXiv ID: 1706.03762
✓ Generated fingerprint: d7729da1a7b25d6f

Testing task input validation...
✓ Valid source passed validation
✓ Invalid source correctly failed validation

Testing literature processing pipeline...
✓ Literature processing completed successfully
✓ Generated literature ID: test_literature_id_123
✓ Database save operation was called
============================================================
ALL TESTS COMPLETED
============================================================
```

## 🔧 调试和故障排除

### 常见问题

#### 1. Redis 连接失败
```bash
# 检查 Redis 是否运行
redis-cli ping
# 应该返回: PONG

# 启动 Redis (如果未运行)
redis-server
```

#### 2. MongoDB 连接问题
```python
# 在任务中会有详细错误日志
logger.error(f"Failed to save literature to database: {e}")
# 会回退到模拟 ID: lit_{task_id}
```

#### 3. 任务超时
```python
# 调整超时设置 (settings.py)
celery_task_time_limit: int = 45 * 60  # 45 分钟
celery_task_soft_time_limit: int = 40 * 60  # 40 分钟
```

### 日志配置

Worker 提供详细的日志输出：
```
[2024-01-15 10:30:00: INFO/MainProcess] Task literature_parser_worker.tasks.process_literature_task[123] started
[2024-01-15 10:30:01: INFO/MainProcess] Task 123: 正在初始化任务 - 解析输入数据
[2024-01-15 10:30:02: INFO/MainProcess] Processing literature from source: https://doi.org/10.1038/nature12373
[2024-01-15 10:30:03: INFO/MainProcess] Extracted identifiers: {'doi': '10.1038/nature12373'}, primary: doi
```

## 📈 性能和扩展

### 性能特性

- **并发控制**: 默认单进程 (`concurrency=1`) 避免外部 API 速率限制
- **内存优化**: 只预取一个任务 (`prefetch_multiplier=1`)
- **超时管理**: 软硬超时避免任务卡死
- **错误重试**: 失败任务可配置重试策略

### 扩展策略

#### 水平扩展
```bash
# 多个 worker 实例
python start_worker.py &  # Worker 1
python start_worker.py &  # Worker 2
python start_worker.py &  # Worker 3
```

#### 垂直扩展
```python
# 增加并发 (谨慎使用，注意 API 限制)
celery_worker_concurrency = 2
```

#### 队列分离
```python
# 不同类型任务使用不同队列
task_routes = {
    "literature_parser_worker.tasks.process_literature_task": {"queue": "literature"},
    "literature_parser_worker.tasks.pdf_processing_task": {"queue": "pdf"},
    "literature_parser_worker.tasks.reference_extraction_task": {"queue": "references"},
}
```

## 🔮 未来改进

1. **实际异步外部 API 调用**: 当前为模拟，需要集成真实的 API 客户端
2. **PDF 下载功能**: 实现从 URL 下载 PDF 文件的功能
3. **增量更新**: 支持对已存在文献的增量更新
4. **批处理支持**: 支持批量处理多个文献
5. **智能去重**: 在任务级别进行文献去重检查
6. **监控集成**: 集成 Flower 或 Prometheus 进行任务监控

---

**这个 Celery 集成为文献解析系统提供了强大、可靠、可扩展的异步任务处理能力，是整个系统架构的核心引擎！** 🚀 