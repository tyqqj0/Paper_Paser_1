# 系统改进 TODO 清单

## 📋 概述

基于批量URL测试的结果和用户反馈，以下是需要改进的系统功能清单。

## ✅ 已完成

### 1. 统一备选自动方案 ✅ **已实现**
- **问题**: 遇到未适配期刊网站时直接失败
- **解决方案**: 实现了GenericAdapter通用适配器
- **效果**: 支持从任何包含DOI的URL中自动提取标识符
- **文档**: 详见 `GENERIC_FALLBACK_SOLUTION.md`

## 🔄 待处理

### 2. 无效URL错误信息优化 🔄 **待实现**

#### 问题描述
当URL对应的文献不存在时（如测试DOI），系统应该在返回信息中明确体现这种情况，而不是简单的"处理失败"。

#### 当前状态
```json
{
  "execution_status": "failed",
  "error_info": "处理超时"  // 不够明确
}
```

#### 期望状态
```json
{
  "execution_status": "failed",
  "error_info": "DOI不存在于CrossRef数据库",
  "error_type": "invalid_doi",
  "suggestions": ["检查DOI格式", "尝试其他数据库"]
}
```

#### 实现计划
1. **错误分类系统**
   - `invalid_doi`: DOI不存在
   - `invalid_arxiv`: ArXiv ID不存在
   - `network_error`: 网络连接问题
   - `parsing_error`: 内容解析失败
   - `timeout_error`: 处理超时

2. **错误检测机制**
   - CrossRef 404响应 → `invalid_doi`
   - ArXiv 404响应 → `invalid_arxiv`
   - 网络异常 → `network_error`

3. **用户友好提示**
   - 提供具体的错误原因
   - 给出可能的解决建议
   - 区分系统错误和数据错误

#### 涉及文件
- `literature_parser_backend/services/crossref.py`
- `literature_parser_backend/worker/metadata_fetcher.py`
- `literature_parser_backend/worker/task_processor.py`

### 3. 并发处理能力研究 🔄 **待研究**

#### 问题描述
需要了解当前后端的并发支持情况，包括：
- 是否支持多个文献同时处理？
- 并发机制是什么样的？
- 并发效果如何？
- 有什么限制？

#### 研究重点

##### 3.1 当前并发架构
- **任务队列**: Redis + Celery/RQ?
- **Worker进程**: 单进程还是多进程？
- **数据库连接**: 连接池配置
- **外部API限制**: CrossRef、Semantic Scholar等的速率限制

##### 3.2 并发性能测试
- **同时处理能力**: 最多能同时处理多少个文献？
- **资源消耗**: CPU、内存、网络使用情况
- **响应时间**: 并发对单个任务处理时间的影响
- **错误率**: 高并发下的失败率

##### 3.3 瓶颈分析
- **外部API限制**: 
  - CrossRef: 50 requests/second (polite pool)
  - Semantic Scholar: 100 requests/second (with API key)
  - GROBID: 取决于服务器配置
- **数据库性能**: MongoDB写入/查询性能
- **内存使用**: PDF处理和GROBID解析的内存需求

##### 3.4 优化建议
- **请求池管理**: 实现智能的API请求分发
- **缓存策略**: 减少重复的外部API调用
- **批处理优化**: 批量处理相似类型的文献
- **资源监控**: 实时监控系统资源使用情况

#### 测试计划
1. **基准测试**
   ```python
   # 测试脚本示例
   async def concurrent_test():
       urls = [list_of_test_urls]  # 50个测试URL
       tasks = [process_literature(url) for url in urls]
       results = await asyncio.gather(*tasks, return_exceptions=True)
       analyze_results(results)
   ```

2. **压力测试**
   - 逐步增加并发数量：1, 5, 10, 20, 50
   - 监控系统资源使用
   - 记录成功率和响应时间

3. **长期稳定性测试**
   - 连续运行24小时
   - 监控内存泄漏
   - 检查错误累积

#### 涉及文件
- `literature_parser_backend/worker/task_processor.py`
- `literature_parser_backend/services/request_manager.py`
- `docker-compose.yml` (worker配置)
- `literature_parser_backend/settings.py` (并发配置)

## 📅 实施时间表

### 第一阶段 (本周)
- [x] ✅ 完成统一备选方案实现
- [ ] 🔄 研究当前并发架构
- [ ] 🔄 设计错误信息优化方案

### 第二阶段 (下周)
- [ ] 📋 实现错误分类系统
- [ ] 📋 进行并发性能测试
- [ ] 📋 优化用户错误提示

### 第三阶段 (后续)
- [ ] 📋 实施并发优化建议
- [ ] 📋 添加系统监控面板
- [ ] 📋 完善文档和测试

## 🎯 优先级

1. **高优先级** 🔴
   - 错误信息优化 (直接影响用户体验)
   
2. **中优先级** 🟡
   - 并发能力研究 (影响系统性能)
   
3. **低优先级** 🟢
   - 长期监控和优化 (系统稳定性)

## 📝 备注

- 所有改进都应该保持向后兼容性
- 需要充分测试，避免影响现有功能
- 考虑添加配置开关，允许渐进式部署
- 及时更新文档和用户指南
