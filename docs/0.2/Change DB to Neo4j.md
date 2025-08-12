
### **技术方案备忘录：文献引用关系系统数据库迁移 (MongoDB -> Neo4j)**

**1. 项目背景与迁移目标**

*   **当前系统**: 一个基于MongoDB的文献管理系统，核心数据为文献（包含元数据和引文列表），运行在云端Docker环境中。
*   **核心痛点**: MongoDB以文档为中心的模型，在处理多层、复杂的引文/被引关系（如“A引用了B，B引用了C，查询A和C之间的所有路径”）时，需要复杂的应用层代码和多次数据库查询，性能低下且难以维护。
*   **迁移目标**: 将数据持久层从MongoDB整体迁移至Neo4j图数据库，以原生、高效的方式对文献引用网络进行建模和查询，并为未来更复杂的关系分析（如社区发现、影响力分析）奠定基础。

**2. 目标技术栈与架构**

*   **主数据库**: Neo4j (通过官方Docker镜像部署)。负责存储所有文献的权威数据模型（节点属性）和关系。
*   **全文/模糊搜索服务**: Elasticsearch (通过官方Docker镜像部署)。负责处理非结构化的引文文本的模糊匹配和搜索，作为Neo4j的“查找预处理器”。
*   **部署环境**: 使用 `docker-compose.yml` 统一编排应用服务、Neo4j服务和Elasticsearch服务，通过环境变量管理数据库连接、密码等配置信息。

**3. 迁移实施路径 (分阶段进行)**

#### **Phase 1: 基础设施搭建与功能对等迁移 (Focus: Like-for-Like Replacement)**

此阶段的目标是**用Neo4j替换MongoDB，并使现有应用功能完全恢复正常**，不引入任何新的图特性。

*   **任务 1.1: 环境准备 (DevOps)**
    *   在 `docker-compose.yml` 中添加 Neo4j 和 Elasticsearch 服务。
    *   配置持久化卷 (volumes) 以确保数据库重启后数据不丢失。
    *   通过环境变量 (`NEO4J_AUTH`, `ELASTIC_PASSWORD` 等) 管理所有服务的认证和配置。

*   **任务 1.2: 数据模型 v1 (Node-Centric Model)**
    *   **节点**: 每篇MongoDB文献对应一个Neo4j节点，标签为 `:Literature`。
    *   **属性**: MongoDB文档的所有字段 (包括 `lid`, `metadata` JSON对象, 以及原有的 `citations` 字符串数组) **直接原封不动地存为该节点的属性**。`citations` 数组此时仅作为临时过渡数据。
    *   **关系**: 此阶段**不创建**任何 `:CITES` 关系。

*   **任务 1.3: 数据迁移脚本 (One-off Script)**
    *   编写一个一次性的迁移脚本 (e.g., Python/Node.js)。
    *   该脚本连接MongoDB和Neo4j，遍历所有文献，并使用 `MERGE` 语句（基于唯一的 `lid`）在Neo4j中创建对应的 `:Literature` 节点，确保脚本的幂等性。

*   **任务 1.4: 重构数据访问层 (Backend)**
    *   将所有原生的MongoDB查询 (e.g., `findOne`, `find`, `updateOne`) 替换为等价的Cypher查询。
    *   **关键**: 此时的查询只针对节点及其属性，例如 `MATCH (n:Literature {lid: $lid}) RETURN n`。
    *   目标是实现与之前完全相同的所有CRUD API。

*   **任务 1.5: 建立基础索引 (Performance)**
    *   为 `:Literature(lid)` 创建唯一性约束（会自动创建索引）。
    *   为其他需要频繁查询的元数据字段（如 `metadata.doi`, `metadata.title`）创建索引，以保证查询性能。

#### **Phase 2: 激活图能力与功能增强 (Focus: Unleash Graph Power)**

此阶段的目标是**利用图的特性，重构核心业务逻辑，并开发新的、基于关系的功能**。

*   **任务 2.1: 数据模型 v2 (Graph-Centric Model)**
    *   **关系**: 定义核心关系类型 `:CITES`。
    *   **节点**: 引入新的节点标签 `:Unresolved`，用于处理数据库中尚不存在的“悬空引用”，形成“占位符节点”模式。

*   **任务 2.2: 关系构建脚本 (One-off Script)**
    *   编写一个后台脚本，遍历所有 `:Literature` 节点。
    *   读取其临时的 `citations` 属性数组，对每个引用的 `lid`，执行 `MATCH (citing:Literature {lid: ...}), (cited:Literature {lid: ...}) MERGE (citing)-[:CITES]->(cited)` 来创建关系。
    *   完成后，可移除临时的 `citations` 属性。

*   **任务 2.3: 实现引文模糊匹配与解析服务 (Backend + Elasticsearch)**
    *   **数据同步**: 实现Neo4j到Elasticsearch的数据同步。当 `:Literature` 节点创建/更新时，将其关键可搜索字段 (`lid`, `title`, `authors`, `year`) 写入/更新到ES的一个索引中。
    *   **模糊匹配API**: 创建一个内部API端点，它接收一个原始引文文本，向ES发起 `fuzzy` 或 `multi_match` 查询，返回一个按相关度排序的、包含`lid`的候选列表。

*   **任务 2.4: 升级核心业务逻辑 (Backend)**
    *   重构“添加/更新文献”的逻辑：
        1.  接收到新文献及其引文列表（可能是文本）。
        2.  对于每条引文，调用**任务2.3**的模糊匹配服务，尝试解析出已存在文献的`lid`。
        3.  如果成功匹配，创建 `:CITES` 关系指向该文献节点。
        4.  如果未匹配，创建一个带 `:Unresolved` 标签的占位符节点，并创建 `:CITES` 关系指向它。
        5.  当一篇新文献被添加时，需检查它是否能“认领”一个已存在的 `:Unresolved` 节点，并将其升级为完整的 `:Literature` 节点。

*   **任务 2.5: 开发新的图查询API (Backend - The Payoff)**
    *   实现之前难以实现的新API，例如：
        *   `GET /literature/{lid}/citations?depth=N`: 获取N度引文网络。
        *   `GET /literature/{lid}/cited_by`: 获取所有引用该文献的列表（反向查询）。
        *   `GET /path/{lid1}/{lid2}`: 查找两篇文献之间的所有引用路径。

**4. 关键技术点与注意事项**

*   **事务性**: 确保复杂的写操作（如创建节点并同时创建多个关系）在单个事务中完成。
*   **性能优化**: 指导工程师使用 `EXPLAIN` 和 `PROFILE` 关键字分析和优化慢查询。索引是性能的第一道防线。
*   **可视化工具**: 强调使用 Neo4j Browser 进行开发、调试和数据探索的便利性，它可以极大地加速对图模型的理解。
*   **测试策略**: 单元测试应覆盖数据访问层的Cypher查询，集成测试需验证从API到ES再到Neo4j的完整工作流。