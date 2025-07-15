# 文献解析系统 - 数据模型说明

## 概述

本文档说明了文献解析系统的核心 Pydantic 数据模型结构。所有模型都位于 `literature_parser_backend/models/` 目录下。

## 模型架构

### 1. 核心数据模型

#### `LiteratureModel` - 主文献模型
- **文件**: `models/literature.py`
- **用途**: MongoDB `literatures` 集合的主文档模型
- **核心字段**:
  - `id`: MongoDB ObjectId (使用自定义 `PyObjectId` 类型)
  - `identifiers`: 权威标识符 (DOI, ArXiv ID, 指纹)
  - `metadata`: 文献元数据 (标题、作者、年份等)
  - `content`: 内容信息 (PDF URL, 解析后的全文等)
  - `references`: 参考文献列表
  - `created_at` / `updated_at`: 时间戳

#### 子模型组件
- `IdentifiersModel`: 权威标识符集合
- `MetadataModel`: 文献元数据
- `ContentModel`: 内容和解析信息
- `ReferenceModel`: 单个参考文献
- `AuthorModel`: 作者信息
- `TaskInfoModel`: 关联任务信息

### 2. API 数据传输对象 (DTOs)

#### 请求 DTOs
- `LiteratureCreateDTO`: 创建文献的请求体
- `LiteratureSourceDTO`: 文献来源信息

#### 响应 DTOs
- `LiteratureSummaryDTO`: 文献摘要响应 (不含大型全文数据)
- `LiteratureFulltextDTO`: 全文内容响应
- `LiteratureCreatedResponseDTO`: 文献已存在的响应
- `LiteratureTaskCreatedResponseDTO`: 新任务创建的响应

### 3. 任务管理模型

#### `TaskStatusDTO` - 任务状态模型
- **文件**: `models/task.py`
- **用途**: API 任务状态查询响应
- **核心字段**:
  - `task_id`: 任务唯一标识符
  - `status`: 任务状态 (pending, processing, success, failure)
  - `stage`: 当前处理阶段 (中文描述)
  - `progress_percentage`: 进度百分比
  - `literature_id`: 完成后的文献ID
  - `error_info`: 错误信息 (失败时)

#### 枚举类型
- `TaskStatus`: 任务状态枚举
- `TaskStage`: 处理阶段枚举 (包含中文进度描述)

#### 内部模型
- `TaskProgressUpdate`: 内部进度更新
- `TaskResult`: 任务完成结果
- `TaskErrorInfo`: 错误信息详情

### 4. 通用组件

#### `PyObjectId` - MongoDB ObjectId 支持
- **文件**: `models/common.py`
- **用途**: Pydantic v2 兼容的 MongoDB ObjectId 类型
- **特性**:
  - 自动序列化为字符串
  - 支持字符串和 ObjectId 输入验证
  - 完整的 JSON Schema 支持
  - API 文档友好

## 使用示例

### 创建文献请求
```python
from models import LiteratureCreateDTO

request = LiteratureCreateDTO(
    source={
        "doi": "10.48550/arXiv.1706.03762",
        "url": "https://arxiv.org/abs/1706.03762"
    }
)
```

### 查询任务状态
```python
from models import TaskStatusDTO, TaskStatus, TaskStage

status = TaskStatusDTO(
    task_id="abc-123",
    status=TaskStatus.PROCESSING,
    stage=TaskStage.FETCHING_METADATA_CROSSREF,
    progress_percentage=30,
    created_at=datetime.now(),
    updated_at=datetime.now()
)
```

### 操作文献模型
```python
from models import LiteratureModel, IdentifiersModel, MetadataModel

literature = LiteratureModel(
    identifiers=IdentifiersModel(
        doi="10.48550/arXiv.1706.03762",
        arxiv_id="1706.03762"
    ),
    metadata=MetadataModel(
        title="Attention Is All You Need",
        authors=[{"full_name": "Ashish Vaswani", "sequence": "first"}],
        year=2017
    )
)
```

## 模型验证

运行以下命令测试所有模型：

```bash
poetry run python -m literature_parser_backend.models.test_models
```

## 关键设计特性

1. **MongoDB 集成**: 使用自定义 `PyObjectId` 无缝处理 MongoDB ObjectId
2. **API 优化**: 分离摘要和全文 DTOs，避免传输大型数据
3. **进度跟踪**: 详细的任务状态和阶段管理，支持中文描述
4. **类型安全**: 完整的 Pydantic v2 类型验证和序列化
5. **文档生成**: 丰富的 JSON Schema 用于自动 API 文档生成
6. **扩展性**: 模块化设计便于添加新的数据类型和字段

## 下一步

这些模型为以下组件提供了基础：
- MongoDB 数据库操作层
- FastAPI 路由和响应处理
- Celery 任务处理
- 外部 API 服务集成 