# Paper Parser API 文档 v0.2 - Neo4j版本

🚀 **基于Neo4j图数据库的智能文献解析与管理系统API文档**

## 📋 基本信息

- **API版本**: v0.2 (Neo4j图数据库版本)
- **Base URL**: `http://localhost:8000/api`
- **文档地址**: `http://localhost:8000/api/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/api/redoc`
- **OpenAPI JSON**: `http://localhost:8000/api/openapi.json`
- **认证**: 暂未实现（未来支持JWT）

## 🏗️ 核心概念

### 文献标识系统
- **LID (Literature ID)**: 系统内部唯一标识符，格式为 `2017-vaswani-aayn-6a05`
- **别名 (Alias)**: 外部标识符映射，如DOI、ArXiv ID、URL等
- **Neo4j节点**: `:Literature`节点存储文献数据，`:Alias`节点建立映射关系

### 任务系统
- **异步处理**: 长时间任务通过Celery队列异步执行
- **实时状态**: 支持SSE流式状态更新
- **智能路由**: 根据文献源选择最优处理路径

## 🔗 API端点总览

| 端点类别 | 端点路径 | 功能描述 |
|---------|---------|----------|
| **文献解析** | `POST /api/resolve` | 统一文献解析入口 |
| **文献查询** | `GET /api/literatures/{lid}` | 文献详情查询 |
| **文献查询** | `GET /api/literatures/by-doi` | DOI便捷查询 |
| **文献查询** | `GET /api/literatures/by-url` | URL便捷查询 |
| **任务管理** | `GET /api/tasks/{task_id}` | 任务状态查询 |
| **任务管理** | `GET /api/tasks/{task_id}/stream` | SSE实时状态 |
| **任务管理** | `DELETE /api/tasks/{task_id}` | 任务取消 |
| **关系图** | `GET /api/graphs` | 文献关系图查询 |
| **文件上传** | `POST /api/upload/request-url` | 文件上传URL |
| **系统监控** | `GET /api/health` | 健康检查 |

---

## 📚 详细API说明

### 1️⃣ 文献解析 API

#### POST /api/resolve
**统一文献解析入口** - 主要API端点

**功能**: 接收外部标识符（DOI、URL等），确保文献在系统中存在

**请求体** (`LiteratureCreateRequestDTO`):
```json
{
  "doi": "10.48550/arXiv.1706.03762",          // DOI标识符（可选）
  "arxiv_id": "1706.03762",                    // ArXiv ID（可选）
  "url": "https://arxiv.org/abs/1706.03762",   // 论文URL（可选）
  "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",  // PDF链接（可选）
  "title": "Attention Is All You Need",        // 标题（可选）
  "authors": ["Ashish Vaswani", "Noam Shazeer"]  // 作者列表（可选）
}
```

**响应示例**:

*情况1: 文献已存在 (200 OK)*
```json
{
  "message": "Literature already exists in system.",
  "lid": "2017-vaswani-aayn-6a05",
  "resource_url": "/api/literatures/2017-vaswani-aayn-6a05",
  "status": "resolved"
}
```

*情况2: 创建新任务 (202 Accepted)*
```json
{
  "message": "Literature resolution task created.",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "status_url": "/api/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "stream_url": "/api/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ef/stream"
}
```

**使用示例**:
```bash
# 通过DOI解析
curl -X POST "http://localhost:8000/api/resolve" \
  -H "Content-Type: application/json" \
  -d '{"doi": "10.48550/arXiv.1706.03762"}'

# 通过URL解析  
curl -X POST "http://localhost:8000/api/resolve" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/1706.03762"}'
```

---

### 2️⃣ 文献查询 API

#### GET /api/literatures/{lid}
**根据LID获取文献详情**

**响应示例** (`LiteratureSummaryDTO`):
```json
{
  "lid": "2017-vaswani-aayn-6a05",
  "metadata": {
    "title": "Attention Is All You Need",
    "authors": [
      {"name": "Ashish Vaswani", "s2_id": "1738948"},
      {"name": "Noam Shazeer", "s2_id": "2456789"}
    ],
    "year": 2017,
    "journal": "Advances in Neural Information Processing Systems",
    "abstract": "The dominant sequence transduction models are based on complex...",
    "keywords": ["transformer", "attention", "neural networks"]
  },
  "identifiers": {
    "doi": "10.48550/arXiv.1706.03762", 
    "arxiv_id": "1706.03762",
    "source_urls": ["https://arxiv.org/abs/1706.03762"]
  },
  "task_info": {
    "status": "completed",
    "components": {
      "metadata": {
        "status": "success",
        "stage": "元数据获取成功",
        "progress": 100,
        "source": "Semantic Scholar"
      },
      "content": {
        "status": "success", 
        "stage": "内容解析完成",
        "progress": 100
      }
    }
  },
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  
  // 便利字段
  "title": "Attention Is All You Need",
  "authors": ["Ashish Vaswani", "Noam Shazeer"], 
  "year": 2017,
  "journal": "Advances in Neural Information Processing Systems",
  "doi": "10.48550/arXiv.1706.03762"
}
```

#### GET /api/literatures/by-doi
**DOI便捷查询接口** - 同步风格接口

**参数**:
- `value` (required): DOI字符串

**示例**:
```bash
curl "http://localhost:8000/api/literatures/by-doi?value=10.48550/arXiv.1706.03762"
```

**行为**: 
- 如果文献存在：立即返回文献数据
- 如果不存在：等待合理时间进行解析，然后返回结果
- 超时后返回任务ID供进一步查询

#### GET /api/literatures/by-url  
**URL便捷查询接口**

**参数**:
- `value` (required): 论文URL

**示例**:
```bash
curl "http://localhost:8000/api/literatures/by-url?value=https://arxiv.org/abs/1706.03762"
```

#### GET /api/literatures/{lid}/fulltext
**获取文献完整内容**

**响应** (`LiteratureFulltextDTO`):
```json
{
  "lid": "2017-vaswani-aayn-6a05",
  "content": {
    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    "fulltext": "Transformer模型的完整文本内容...",
    "parsing_method": "GROBID",
    "quality_score": 85
  },
  "references": [
    {
      "title": "Long Short-term Memory",
      "authors": ["Sepp Hochreiter", "Jürgen Schmidhuber"], 
      "year": 1997
    }
  ]
}
```

#### GET /api/literatures
**批量查询文献**

**参数**:
- `lids`: 逗号分隔的LID列表
- `limit`: 结果数量限制 (默认10, 最大100)

**示例**:
```bash
curl "http://localhost:8000/api/literatures?lids=2017-vaswani-aayn-6a05,2019-do-gtpncr-72ef&limit=20"
```

---

### 3️⃣ 任务管理 API

#### GET /api/tasks/{task_id}
**获取任务状态**

**响应** (`TaskStatusDTO`):
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "execution_status": "processing",
  "status": "processing", 
  "overall_progress": 65,
  "current_stage": "正在从Semantic Scholar获取元数据",
  "literature_id": null,
  "result_type": null,
  "literature_status": {
    "literature_id": "2017-vaswani-aayn-6a05",
    "overall_status": "processing",
    "overall_progress": 65,
    "component_status": {
      "metadata": {
        "status": "processing",
        "stage": "正在从Semantic Scholar获取元数据", 
        "progress": 80,
        "source": "Semantic Scholar"
      },
      "content": {
        "status": "pending",
        "stage": "等待元数据完成",
        "progress": 0
      },
      "references": {
        "status": "pending", 
        "stage": "等待内容解析完成",
        "progress": 0
      }
    }
  },
  "error_info": null
}
```

**任务状态值**:
- `pending`: 任务等待中
- `processing`: 任务处理中  
- `completed`: 任务完成
- `failed`: 任务失败

#### GET /api/tasks/{task_id}/stream
**SSE实时状态更新**

**功能**: 建立Server-Sent Events连接，实时推送任务状态

**事件类型**:
- `progress`: 进度更新
- `completed`: 任务完成  
- `failed`: 任务失败

**使用示例**:
```javascript
// JavaScript客户端示例
const eventSource = new EventSource('/api/tasks/a1b2c3d4-e5f6-7890/stream');

eventSource.addEventListener('progress', function(event) {
  const data = JSON.parse(event.data);
  console.log(`进度: ${data.progress}% - ${data.stage}`);
});

eventSource.addEventListener('completed', function(event) {
  const data = JSON.parse(event.data);
  console.log(`任务完成: LID=${data.literature_id}`);
  eventSource.close();
});
```

**Python客户端示例** (参考test_various_links.py):
```python
import aiohttp
import json

async def stream_task_status(task_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://localhost:8000/api/tasks/{task_id}/stream",
            headers={"Accept": "text/event-stream"}
        ) as response:
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                if line_str.startswith('data:'):
                    data = json.loads(line_str[5:])
                    print(f"状态更新: {data}")
```

#### DELETE /api/tasks/{task_id}
**取消任务**

**响应**:
```json
{
  "message": "Task a1b2c3d4-e5f6-7890-abcd-1234567890ef cancellation requested",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef", 
  "status": "cancelled"
}
```

---

### 4️⃣ 图关系 API

#### GET /api/graphs
**获取文献关系图**

**参数**:
- `lids` (required): 逗号分隔的LID列表（最多20个）

**响应示例**:
```json
{
  "nodes": [
    {
      "id": "2017-vaswani-aayn-6a05",
      "title": "Attention Is All You Need", 
      "authors": ["Ashish Vaswani", "Noam Shazeer"],
      "year": 2017,
      "type": "literature"
    },
    {
      "id": "2014-sutskever-snmtbg-a1b2", 
      "title": "Sequence to Sequence Learning",
      "authors": ["Ilya Sutskever", "Oriol Vinyals"],
      "year": 2014,
      "type": "literature"
    }
  ],
  "edges": [
    {
      "source": "2017-vaswani-aayn-6a05",
      "target": "2014-sutskever-snmtbg-a1b2", 
      "type": "CITES",
      "weight": 1.0
    }
  ],
  "metadata": {
    "total_nodes": 2,
    "total_edges": 1, 
    "requested_lids": ["2017-vaswani-aayn-6a05", "2014-sutskever-snmtbg-a1b2"],
    "total_requested": 2,
    "relationship_type": "internal_only",
    "api_version": "0.2",
    "status": "success"
  }
}
```

**使用示例**:
```bash
curl "http://localhost:8000/api/graphs?lids=2017-vaswani-aayn-6a05,2014-sutskever-snmtbg-a1b2"
```

**Neo4j查询示例** (直接数据库访问):
```cypher
// 查看引用关系
MATCH (a:Literature)-[:CITES]->(b:Literature) 
WHERE a.lid IN ['2017-vaswani-aayn-6a05', '2014-sutskever-snmtbg-a1b2']
   OR b.lid IN ['2017-vaswani-aayn-6a05', '2014-sutskever-snmtbg-a1b2']
RETURN a, b
```

---

### 5️⃣ 文件上传 API

#### POST /api/upload/request-url
**请求文件上传预签名URL**

**请求体**:
```json
{
  "fileName": "paper.pdf",
  "contentType": "application/pdf",
  "fileSize": 2048000,
  "userId": "user123"
}
```

**响应** (`UploadResponseDTO`):
```json
{
  "uploadUrl": "https://cos-domain.com/upload/signed-url",
  "publicUrl": "https://cos-domain.com/papers/user123/paper.pdf",  
  "objectKey": "papers/user123/paper.pdf",
  "expires": "2024-01-15T11:30:00Z",
  "maxFileSize": 10485760
}
```

#### GET /api/upload/status
**查询上传状态**

**参数**:
- `public_url`: 公开访问URL（二选一）
- `object_key`: 对象存储键名（二选一）

**响应**:
```json
{
  "objectKey": "papers/user123/paper.pdf",
  "exists": true,
  "size": 2048000,
  "contentType": "application/pdf", 
  "lastModified": "2024-01-15T10:45:00Z",
  "publicUrl": "https://cos-domain.com/papers/user123/paper.pdf"
}
```

---

### 6️⃣ 系统监控 API

#### GET /api/health
**系统健康检查**

**响应**: HTTP 200 (系统正常)

---

## 🔄 完整工作流示例

### 场景1: 前端UI异步处理
```bash
# 1. 提交解析请求
curl -X POST "http://localhost:8000/api/resolve" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/1706.03762"}'

# 响应: {"task_id": "abc-123", "stream_url": "/api/tasks/abc-123/stream"}

# 2. 建立SSE连接监听进度（前端JavaScript）
const eventSource = new EventSource('/api/tasks/abc-123/stream');

# 3. 任务完成后获取文献数据
curl "http://localhost:8000/api/literatures/2017-vaswani-aayn-6a05"
```

### 场景2: 脚本简单调用
```bash
# 直接使用便捷接口（同步风格）
curl "http://localhost:8000/api/literatures/by-doi?value=10.48550/arXiv.1706.03762"
# 自动等待解析完成并返回数据
```

### 场景3: 批量查询和关系分析
```bash
# 1. 批量查询多篇文献
curl "http://localhost:8000/api/literatures?lids=lit1,lit2,lit3"

# 2. 分析内部引用关系  
curl "http://localhost:8000/api/graphs?lids=lit1,lit2,lit3"
```

---

## ⚠️ 错误处理

### HTTP状态码
- `200 OK`: 请求成功
- `202 Accepted`: 异步任务已创建
- `400 Bad Request`: 请求参数错误
- `404 Not Found`: 资源不存在
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式
```json
{
  "detail": "错误描述信息",
  "error_type": "ValidationError",
  "error_code": "INVALID_DOI_FORMAT"
}
```

### 常见错误类型
- `ValidationError`: 参数验证失败
- `HTTPError`: HTTP请求失败
- `GROBIDConnectionError`: PDF解析服务不可用
- `URLValidationError`: URL格式错误
- `TaskExecutionError`: 任务执行失败
- `ParseError`: 内容解析失败

---

## 🚀 智能路由系统

系统根据文献源自动选择最优处理路径：

### 快速路径 (高置信度源)
- **ArXiv**: `arxiv.org/abs/*` → Semantic Scholar
- **DOI直链**: `doi.org/*` → CrossRef + Semantic Scholar

### 增强路径 (需要特殊处理)  
- **会议论文**: `proceedings.neurips.cc/*` → CrossRef精确匹配
- **期刊网站**: `nature.com/*` → 专用适配器

### 通用回退路径
- **其他URL**: 瀑布流处理器（多处理器并行）

---

## 📊 数据模型摘要

### 核心模型
- **LiteratureModel**: 文献主体数据
- **IdentifiersModel**: 标识符集合
- **MetadataModel**: 元数据信息
- **TaskStatusDTO**: 任务状态信息
- **ComponentDetail**: 组件处理详情

### Neo4j数据结构
- **节点类型**: `:Literature`, `:Alias` 
- **关系类型**: `:IDENTIFIES`, `:CITES`
- **索引**: LID, DOI, ArXiv ID上的唯一索引

---

## 🎯 性能特性

- **并发处理**: Celery分布式任务队列
- **智能缓存**: 别名系统避免重复解析
- **流式传输**: SSE实时状态更新
- **图查询优化**: Neo4j原生图遍历
- **批量操作**: 支持批量查询和分析

---

## 🔧 配置参考

### 服务端口
- **API服务**: `http://localhost:8000`
- **Neo4j Browser**: `http://localhost:7474` 
- **Elasticsearch**: `http://localhost:9200`
- **Redis Commander**: `http://localhost:8081`

### 认证信息
- **Neo4j**: `neo4j / literature_parser_neo4j`
- **Elasticsearch**: `elastic / literature_parser_elastic`

---

**🎉 恭喜！您现在拥有了完整的Neo4j版文献解析系统API文档！**

> 💡 **提示**: 建议先通过Swagger UI (`/api/docs`) 进行交互式探索，然后使用此文档作为集成参考。


