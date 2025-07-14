# Literature Parser API 文档

## 概述

文献解析后端系统提供了完整的REST API，支持文献提交、处理状态查询和结果获取。系统采用异步任务处理架构，确保高并发和可扩展性。

## 基础信息

- **Base URL**: `http://localhost:8000/api`
- **认证**: 暂未实现（计划支持JWT）
- **请求格式**: JSON
- **响应格式**: JSON
- **API文档**: `http://localhost:8000/docs` (Swagger UI)

## API 端点详解

### 1. 文献处理接口

#### 1.1 提交文献处理请求

**端点**: `POST /api/literature`

**描述**: 提交新的文献处理请求。系统会先进行查重，如果文献已存在则直接返回，否则启动后台处理任务。

**请求体** (`LiteratureCreateDTO`):
```json
{
  "doi": "10.1038/nature12373",           // DOI标识符（可选，但推荐）
  "arxiv_id": "1234.5678v1",              // ArXiv ID（可选）
  "pdf_url": "https://example.com/paper.pdf",  // PDF文件URL（可选）
  "title": "论文标题",                     // 论文标题（可选）
  "authors": ["作者1", "作者2"]            // 作者列表（可选）
}
```

**响应示例**:

*情况1: 文献已存在 (200 OK)*
```json
{
  "message": "文献已存在",
  "literatureId": "60f7b1c9e1b2c3d4e5f6a7b8",
  "status": "exists"
}
```

*情况2: 启动新任务 (202 Accepted)*
```json
{
  "message": "文献处理任务已启动",
  "taskId": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status": "processing"
}
```

**错误响应**:
```json
{
  "detail": "内部服务错误: 具体错误信息"
}
```

#### 1.2 获取文献摘要

**端点**: `GET /api/literature/{literature_id}`

**描述**: 获取指定文献的摘要信息，包含元数据但不包含完整内容。

**路径参数**:
- `literature_id`: 文献的MongoDB ObjectId

**响应示例** (`LiteratureSummaryDTO`):
```json
{
  "id": "60f7b1c9e1b2c3d4e5f6a7b8",
  "identifiers": {
    "doi": "10.1038/nature12373",
    "arxiv_id": null,
    "fingerprint": "abc123def456"
  },
  "metadata": {
    "title": "A breakthrough in quantum computing",
    "authors": [
      {"name": "John Doe", "affiliation": "MIT"},
      {"name": "Jane Smith", "affiliation": "Stanford"}
    ],
    "abstract": "This paper presents...",
    "publication_date": "2023-01-15",
    "journal": "Nature",
    "keywords": ["quantum", "computing"],
    "language": "en"
  },
  "task_info": {
    "status": "completed",
    "processing_stages": ["标识符提取", "元数据获取", "引用解析", "数据集成"],
    "created_at": "2024-01-01T10:00:00Z",
    "completed_at": "2024-01-01T10:05:30Z"
  },
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:05:30Z"
}
```

#### 1.3 获取文献完整内容

**端点**: `GET /api/literature/{literature_id}/fulltext`

**描述**: 获取指定文献的完整解析内容，包含正文、结构化数据和引用信息。

**路径参数**:
- `literature_id`: 文献的MongoDB ObjectId

**响应示例** (`LiteratureFulltextDTO`):
```json
{
  "id": "60f7b1c9e1b2c3d4e5f6a7b8",
  "identifiers": { /* 同摘要 */ },
  "metadata": { /* 同摘要 */ },
  "content": {
    "abstract": "完整摘要内容...",
    "fulltext": "完整正文内容...",
    "sections": [
      {
        "title": "Introduction",
        "content": "介绍部分内容...",
        "level": 1
      },
      {
        "title": "Methodology",
        "content": "方法部分内容...",
        "level": 1
      }
    ],
    "figures": [
      {
        "caption": "Figure 1: Experimental setup",
        "url": "https://example.com/figure1.png"
      }
    ],
    "tables": [
      {
        "caption": "Table 1: Results summary",
        "content": "表格数据..."
      }
    ]
  },
  "references": [
    {
      "title": "Reference paper 1",
      "authors": ["Author A", "Author B"],
      "doi": "10.1000/reference1",
      "year": 2022,
      "journal": "Science"
    }
  ],
  "task_info": { /* 同摘要 */ },
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:05:30Z"
}
```

### 2. 任务管理接口

#### 2.1 查询任务状态

**端点**: `GET /api/task/{task_id}`

**描述**: 查询Celery任务的执行状态和结果。

**路径参数**:
- `task_id`: Celery任务ID

**响应示例** (`TaskStatusDTO`):

*进行中任务*:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status": "processing",
  "message": "正在执行: 元数据获取",
  "progress": {
    "current": 40,
    "total": 100,
    "description": "正在从CrossRef获取元数据"
  },
  "literature_id": null,
  "error": null,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:02:30Z"
}
```

*完成任务*:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status": "success",
  "message": "任务执行成功",
  "progress": {
    "current": 100,
    "total": 100,
    "description": "处理完成"
  },
  "literature_id": "60f7b1c9e1b2c3d4e5f6a7b8",
  "error": null,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:05:30Z"
}
```

*失败任务*:
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status": "failure",
  "message": "任务执行失败",
  "progress": null,
  "literature_id": null,
  "error": "无法解析PDF文件: 文件格式不支持",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-01T10:03:15Z"
}
```

**任务状态说明**:
- `pending`: 任务等待执行
- `processing`: 任务正在执行
- `success`: 任务执行成功
- `failure`: 任务执行失败
- `cancelled`: 任务被取消

#### 2.2 取消任务

**端点**: `DELETE /api/task/{task_id}`

**描述**: 取消正在执行的任务。

**路径参数**:
- `task_id`: Celery任务ID

**响应示例**:
```json
{
  "message": "任务取消成功",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status": "cancelled"
}
```

## 工作流程示例

### 典型的文献处理流程

1. **提交文献请求**:
   ```bash
   curl -X POST "http://localhost:8000/api/literature" \
        -H "Content-Type: application/json" \
        -d '{"doi": "10.1038/nature12373"}'
   ```

2. **获得任务ID并轮询状态**:
   ```bash
   curl "http://localhost:8000/api/task/a1b2c3d4-e5f6-7890-abcd-1234567890ef"
   ```

3. **任务完成后获取结果**:
   ```bash
   curl "http://localhost:8000/api/literature/60f7b1c9e1b2c3d4e5f6a7b8"
   ```

4. **需要时获取完整内容**:
   ```bash
   curl "http://localhost:8000/api/literature/60f7b1c9e1b2c3d4e5f6a7b8/fulltext"
   ```

## 错误处理

### HTTP状态码

- `200 OK`: 请求成功
- `202 Accepted`: 任务已接受，正在处理
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 数据验证失败
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式

```json
{
  "detail": "错误详细信息"
}
```

## 性能考虑

### 查重机制
- 系统会根据DOI和ArXiv ID进行查重
- 建议客户端在提交前也进行本地查重
- 重复提交已存在的文献会立即返回结果

### 异步处理
- 所有文献处理都是异步的
- 建议使用轮询方式查询任务状态
- 轮询间隔建议为3-5秒

### 限流建议
- 建议每个客户端不超过10个并发任务
- 频繁的状态查询可能被限流
- 使用WebSocket连接获取实时更新（计划功能）

## SDK 和工具

### Python SDK 示例

```python
import httpx
import asyncio
import time

class LiteratureParserClient:
    def __init__(self, base_url="http://localhost:8000/api"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def submit_literature(self, literature_data):
        """提交文献处理请求"""
        response = await self.client.post(
            f"{self.base_url}/literature",
            json=literature_data
        )
        return response.json()
    
    async def get_task_status(self, task_id):
        """获取任务状态"""
        response = await self.client.get(f"{self.base_url}/task/{task_id}")
        return response.json()
    
    async def wait_for_completion(self, task_id, timeout=300):
        """等待任务完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = await self.get_task_status(task_id)
            if status["status"] in ["success", "failure", "cancelled"]:
                return status
            await asyncio.sleep(3)
        raise TimeoutError("任务执行超时")
    
    async def get_literature(self, literature_id, fulltext=False):
        """获取文献信息"""
        url = f"{self.base_url}/literature/{literature_id}"
        if fulltext:
            url += "/fulltext"
        response = await self.client.get(url)
        return response.json()

# 使用示例
async def main():
    client = LiteratureParserClient()
    
    # 提交文献
    result = await client.submit_literature({
        "doi": "10.1038/nature12373"
    })
    
    if result["status"] == "exists":
        print(f"文献已存在: {result['literatureId']}")
        return result["literatureId"]
    
    # 等待处理完成
    task_result = await client.wait_for_completion(result["taskId"])
    
    if task_result["status"] == "success":
        print(f"处理成功: {task_result['literature_id']}")
        return task_result["literature_id"]
    else:
        print(f"处理失败: {task_result['error']}")
        return None

if __name__ == "__main__":
    asyncio.run(main())
```

## 部署注意事项

### 环境变量

```bash
# Redis配置
REDIS_URL=redis://localhost:6379/0

# MongoDB配置  
MONGODB_URL=mongodb://localhost:27017/literature_parser

# 外部API配置
GROBID_URL=http://localhost:8070
CROSSREF_EMAIL=your-email@example.com
SEMANTIC_SCHOLAR_API_KEY=your-api-key

# Celery配置
CELERY_RESULT_EXPIRES=3600
CELERY_TASK_TIMEOUT=300
```

### 服务依赖

1. **Redis**: 消息队列和结果存储
2. **MongoDB**: 数据持久化
3. **GROBID**: PDF解析服务
4. **Celery Worker**: 后台任务处理

### 监控端点

- **健康检查**: `GET /api/monitoring/health`
- **系统状态**: `GET /api/monitoring/status`
- **API文档**: `GET /docs`

---

*本文档持续更新中，如有问题请提交Issue或Pull Request。* 