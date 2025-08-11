# 项目代号："Lighthouse" - 智能文献导航系统
## 1. 系统愿景 (Vision)
构建一个高效、可扩展的文献处理与关联分析系统。该系统能够将来自不同来源的文献标识符（如URL, DOI）统一管理，并揭示文献之间的内在联系，为上层应用提供强大的数据支持。

## 2. 核心概念 (Core Concepts)
系统围绕以下几个核心数据实体构建：

### 文献 (Literature)

描述: 系统中所有知识的原子单元。每篇文献代表一个独立的学术作品。
关键属性:
LID (Literature ID): 系统内部唯一、不可变的标识符。这是文献在系统中的“身份证号”。
元数据 (Metadata): 包括但不限于标题、作者、摘要、发表日期等描述性信息。
### 文献别名 (Alias)

描述: 文献在外部世界的各种“名字”或“地址”。
目的: 将多种外部标识符统一映射到唯一的LID上。
示例: DOI (10.1038/nature12345), ArXiv ID (1706.03762), PubMed URL等。
### 任务 (Task)

描述: 一个用于追踪后台异步处理流程（如文献解析）的记录。
关键属性:
Task ID: 任务的唯一标识符。
状态 (Status): 任务的当前生命周期阶段（例如：PENDING, PROCESSING, COMPLETED, FAILED）。
进度 (Progress): 对任务处理过程的更细粒度描述（例如：下载中, 解析中）。
结果 (Result): 任务成功后产出的数据，例如新创建的LID。
### 关系 (Relationship)

描述: 文献与文献之间的连接。
示例: (LID_A) -[CITES]-> (LID_B) 表示文献A引用了文献B。
## 3. 核心业务操作 (Core Operations)
系统需要支持以下三大核心业务流程：

### 确保文献存在 (Ensure Literature Exists)

输入: 一个外部文献别名（如DOI）。
目标: 确保该别名对应的文献在系统中存在，并返回其LID。
逻辑:
如果别名已存在映射，立即返回对应的LID。
如果别名不存在，则启动一个后台解析任务，并返回该任务的Task ID。
### 获取文献数据 (Get Literature Data)

输入: 一个或多个LID。
目标: 返回指定文献的详细元数据。
### 获取文献关系图 (Get Literature Graph)

输入: 一个或多个LID。
目标: 返回这些文献之间已知的相互关系（如图谱数据）。
## 4. API 接口设计 (API Endpoints)
系统对外暴露一组RESTful API，分为以下几类：

### 解析与任务创建 (Resolution & Task Creation)

POST /api/resolve
功能: 接收一个或多个外部别名，触发“确保文献存在”操作。
预期响应:
若别名已全部存在，返回 200 OK 及对应的LID列表。
若有任何别名需要解析，返回 202 Accepted 及一个全局Task ID。
### 任务状态追踪 (Task Tracking)

GET /api/tasks/{task_id}
功能: 查询指定任务的当前状态、进度和最终结果。
GET /api/tasks/{task_id}/stream
功能: (可选高级功能) 建立一个SSE（Server-Sent Events）连接，用于实时接收任务状态的更新推送。
### 数据查询 (Data Retrieval)

GET /api/literatures/{lid}
功能: 根据LID获取单篇文献的元数据。
GET /api/literatures?lids={lid1},{lid2},...
功能: 批量获取多篇文献的元数据。
GET /api/graphs?lids={lid1},{lid2},...
功能: 获取指定文献集合内部的相互关系图。
### 便捷查询接口 (Convenience Endpoints)

GET /api/literatures/by-doi?value={doi_string}
功能: 一个“同步风格”的便捷接口。它会尝试直接返回文献数据。如果文献需要后台解析，该接口会等待一段合理的时间，直到解析完成再返回数据。
（可为其他别名类型如URL、PMID等设计类似的便捷接口）
## 5. 典型工作流程 (Typical Workflow)
### 场景1：需要实时进度的前端UI

UI: 用户提交一个DOI。
前端: 调用 POST /api/resolve 并传入该DOI。
系统:
情况A (命中): 系统发现DOI已存在，直接返回 200 OK 和对应的LID。前端拿到LID后，调用 GET /api/literatures/{lid} 获取数据并渲染。
情况B (未命中): 系统返回 202 Accepted 和一个Task ID。
前端: 接收到Task ID，立即调用 GET /api/tasks/{task_id}/stream (或轮询 GET /api/tasks/{task_id}) 来实时更新UI上的进度条或状态信息（“解析中...”、“已完成”）。
前端: 当任务状态变为COMPLETED时，从任务结果中获取新的LID，再调用 GET /api/literatures/{lid} 获取数据并渲染。
### 场景2：简单的脚本或后端服务调用

脚本: 需要获取某个DOI的文献标题。
脚本: 调用便捷接口 GET /api/literatures/by-doi?value=...。
系统: 在内部完成所有必要步骤（检查缓存、创建任务、等待任务完成、查询数据）。
脚本: 在一次HTTP请求-响应周期内，直接获得包含标题的完整文献JSON数据。
