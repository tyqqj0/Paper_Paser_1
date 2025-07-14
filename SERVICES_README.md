# 外部 API 服务客户端

本文档说明了文献解析系统中外部 API 服务客户端的设计和使用方法。

## 概述

我们为文献解析系统创建了三个专业的外部 API 客户端，每个都针对特定的学术服务进行了优化：

1. **GROBID 客户端** (`services/grobid.py`) - PDF 文档解析和元数据提取
2. **CrossRef 客户端** (`services/crossref.py`) - 权威学术元数据检索
3. **Semantic Scholar 客户端** (`services/semantic_scholar.py`) - AI 驱动的学术图谱数据

## 🔧 技术实现

### 核心技术栈
- **HTTP 客户端**: `httpx` - 现代异步 HTTP 库
- **XML 解析**: `xmltodict` - 用于处理 GROBID 的 TEI XML 响应
- **配置管理**: 集成到 `settings.py` 中，支持环境变量配置
- **错误处理**: 完整的异常处理和日志记录
- **类型提示**: 全面的 Python 类型注解

### 设计原则
- **异步优先**: 所有网络请求都使用 `async/await`
- **容错性**: 优雅处理网络错误、超时和 API 限制
- **可配置**: 通过 settings.py 统一配置所有外部服务
- **标准化**: 统一的数据格式和错误处理模式

## 📚 客户端详细说明

### 1. GROBID 客户端

**用途**: 从 PDF 文档中提取结构化的学术内容

**核心功能**:
```python
# 健康检查
is_healthy = await client.health_check()

# 完整文档处理
result = await client.process_pdf(
    pdf_file=pdf_bytes,
    include_raw_citations=True,
    consolidate_header=1
)

# 仅提取标题元数据  
header_data = await client.process_header_only(pdf_bytes)
```

**输出格式**:
- **TEI XML**: GROBID 原生的 TEI (Text Encoding Initiative) 格式
- **结构化数据**: 解析后的标题、作者、摘要、引用等
- **坐标信息**: 可选的 PDF 坐标，用于定位原文位置

**特色功能**:
- 智能 TEI XML 解析，提取标题、作者、机构信息
- 引用文献的自动识别和结构化
- 支持多种整合级别的元数据扩充
- PDF 坐标提取，支持原文定位

### 2. CrossRef 客户端

**用途**: 获取权威的学术出版物元数据

**核心功能**:
```python
# 通过 DOI 获取元数据
metadata = await client.get_metadata_by_doi("10.1000/example")

# 搜索相关文献
results = await client.search_by_title_author(
    title="Machine Learning",
    author="John Doe",
    year=2023
)

# 检查 DOI 注册机构
agency = await client.check_doi_agency("10.1000/example")
```

**API 特性**:
- **Polite Pool**: 使用正确的 User-Agent 获得更快的响应速度
- **元数据丰富**: 包含作者、机构、资助信息、许可证等
- **引用统计**: 引用数量和被引用数量
- **开放获取**: 自动识别开放获取状态

**输出规范化**:
- 统一的作者信息格式（姓名、ORCID、机构）
- 标准化的日期格式
- 详细的出版信息（期刊、卷号、页码等）

### 3. Semantic Scholar 客户端

**用途**: 获取 AI 增强的学术数据和引用网络

**核心功能**:
```python
# 多种标识符支持
metadata = await client.get_metadata("10.1000/example", id_type="doi")
metadata = await client.get_metadata("arxiv:2301.10140", id_type="arxiv")

# 获取引用和参考文献
references = await client.get_references(paper_id, limit=100)
citations = await client.get_citations(paper_id, limit=100)

# 智能搜索
papers = await client.search_papers(
    query="transformer neural networks",
    year="2020-2023",
    limit=10
)
```

**AI 增强功能**:
- **智能标识符检测**: 自动识别 DOI、ArXiv ID、Semantic Scholar ID
- **影响力指标**: 引用数、有影响力的引用数、h-index
- **研究领域**: AI 分类的研究领域标签
- **TLDR 摘要**: AI 生成的简明摘要
- **开放获取**: PDF 可用性检测

## ⚙️ 配置说明

### settings.py 配置项

```python
# 外部服务 URL
grobid_base_url: str = "http://localhost:8070"
crossref_api_base_url: str = "https://api.crossref.org"  
semantic_scholar_api_base_url: str = "https://api.semanticscholar.org"

# API 密钥和认证
crossref_mailto: str = "your-email@example.com"  # CrossRef 礼貌池必需
semantic_scholar_api_key: str = ""  # 可选，但推荐

# 请求配置
external_api_timeout: int = 30  # 超时时间（秒）
external_api_max_retries: int = 3  # 最大重试次数
```

### 环境变量支持

```bash
# 生产环境建议通过环境变量配置
export CROSSREF_MAILTO="your-email@example.com"
export SEMANTIC_SCHOLAR_API_KEY="your-api-key"
export GROBID_BASE_URL="http://grobid-service:8070"
```

## 🚀 使用示例

### 基本用法

```python
from literature_parser_backend.services import (
    GrobidClient, CrossRefClient, SemanticScholarClient
)

# 初始化客户端
grobid = GrobidClient()
crossref = CrossRefClient()
semantic_scholar = SemanticScholarClient()

# 处理 PDF 文档
async def process_literature(pdf_bytes: bytes, doi: str):
    # 1. 从 PDF 提取初始元数据
    grobid_result = await grobid.process_pdf(pdf_bytes)
    
    # 2. 通过 CrossRef 获取权威元数据
    crossref_metadata = await crossref.get_metadata_by_doi(doi)
    
    # 3. 从 Semantic Scholar 获取引用网络
    s2_metadata = await semantic_scholar.get_metadata(doi)
    references = await semantic_scholar.get_references(doi)
    
    return {
        "grobid": grobid_result,
        "crossref": crossref_metadata,
        "semantic_scholar": s2_metadata,
        "references": references
    }
```

### 错误处理

```python
async def safe_api_call():
    try:
        result = await crossref.get_metadata_by_doi("10.1000/example")
        return result
    except ValueError as e:
        # 输入验证错误
        logger.error(f"Invalid input: {e}")
    except Exception as e:
        # 网络或 API 错误
        logger.error(f"API error: {e}")
        return None
```

## 🧪 测试

运行完整的客户端测试：

```bash
# 运行所有客户端测试
python -m literature_parser_backend.services.test_clients

# 或使用 poetry
poetry run python -m literature_parser_backend.services.test_clients
```

测试涵盖：
- ✅ 客户端初始化
- ✅ 输入验证
- ✅ 错误处理
- ✅ API 连通性（在服务可用时）
- ✅ 数据格式解析

## 📈 性能考虑

### 速率限制
- **CrossRef**: 使用 polite pool，推荐 50 请求/秒
- **Semantic Scholar**: 无 API key 时 100 请求/5分钟，有 key 时 1 请求/秒
- **GROBID**: 取决于服务器配置，建议并发控制

### 最佳实践
1. **使用 API Key**: Semantic Scholar API key 提供更高的速率限制
2. **批量处理**: 优先使用批量端点（如 Semantic Scholar 的 batch API）
3. **缓存结果**: 对相同标识符的请求应该缓存结果
4. **异步并发**: 合理控制并发数量，避免触发速率限制
5. **优雅降级**: API 失败时有备用方案

## 🔮 扩展性

### 添加新的 API 服务

1. 在 `services/` 下创建新的客户端模块
2. 遵循现有的异步模式和错误处理
3. 在 `services/__init__.py` 中导出新客户端
4. 在 `settings.py` 中添加配置项
5. 编写相应的测试用例

### 自定义数据解析

每个客户端都提供 `raw_data` 字段，包含 API 的原始响应，支持自定义解析逻辑：

```python
# 访问原始 CrossRef 数据
raw_crossref = metadata["raw_data"]
custom_field = raw_crossref.get("custom-field")

# 访问原始 GROBID TEI XML
raw_xml = grobid_result["raw_xml"]
# 进行自定义 XML 解析
```

## 📋 依赖项

```toml
[tool.poetry.dependencies]
httpx = "^0.28.1"      # 现代异步 HTTP 客户端
xmltodict = "^0.14.2"  # XML 到字典转换（用于 GROBID TEI）
```

## 🔗 相关链接

- [GROBID 官方文档](https://grobid.readthedocs.io/)
- [CrossRef REST API 文档](https://github.com/CrossRef/rest-api-doc)  
- [Semantic Scholar API 文档](https://www.semanticscholar.org/product/api)
- [TEI Guidelines](https://tei-c.org/guidelines/) 