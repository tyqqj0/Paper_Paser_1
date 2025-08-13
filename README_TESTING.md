# 📋 端到端引用关系系统测试指南

这个指南将帮助你运行完整的端到端测试，验证文献引用关系系统的各个组件。

## 🎯 测试目标

1. **文献添加流程** - 验证文献能正确添加到系统
2. **引用关系解析** - 验证参考文献能正确匹配和链接
3. **Neo4j图数据** - 验证引用关系在图数据库中正确存储
4. **Graphs API** - 验证图查询API返回正确的关系数据

## 🔧 环境准备

### 1. 安装测试依赖
```bash
pip install -r requirements_test.txt
```

### 2. 确保服务运行
在运行测试前，确保以下服务正在运行：

```bash
# 启动完整服务栈
sudo docker compose up -d

# 检查服务状态
sudo docker compose ps
```

应该看到以下服务都在运行：
- `paper_parser_backend` (FastAPI服务)
- `redis` (任务队列)
- `celery_worker` (后台处理)
- `mongodb` (文献数据存储)
- `neo4j` (引用关系图数据库)
- `grobid` (PDF解析服务)

### 3. 验证API可访问
```bash
curl http://localhost:8000/health
```

## 🚀 运行测试

### 完整端到端测试
```bash
python test_end_to_end_citation_system.py --mode full
```

这个测试将：
1. 添加5篇有引用关系的经典论文
2. 等待引用关系处理完成
3. 验证引用关系是否正确建立
4. 测试Graphs API功能
5. 生成详细测试报告

### 仅测试Graphs API
```bash
python test_end_to_end_citation_system.py --mode graphs-only
```

### Neo4j数据直接检查
```bash
python test_neo4j_relationships.py
```

这个工具将：
- 显示Neo4j中所有文献节点
- 显示所有引用关系
- 测试引用图查询功能
- 分析每个文献的引用统计

## 📊 测试数据

测试使用以下经典论文，它们有明确的引用关系：

1. **Word2Vec** (2013) - 基础词向量论文
2. **Attention Mechanism** (2014) - 注意力机制，引用Word2Vec
3. **Transformer** (2017) - "Attention Is All You Need"，引用注意力机制
4. **BERT** (2018) - 引用Word2Vec和Transformer
5. **GPT-2** (2019) - 引用Transformer和BERT

## 📈 预期结果

### 成功的测试应该显示：

```
📚 文献添加: 5 篇成功
   ✅ Word2Vec: LID=2013-mikolov-efficient-abcd
   ✅ Attention Mechanism: LID=2014-bahdanau-neural-efgh
   ✅ Transformer: LID=2017-vaswani-attention-ijkl
   ✅ BERT: LID=2018-devlin-bert-mnop
   ✅ GPT-2: LID=2019-radford-language-qrst

🔗 引用关系验证:
   预期关系: 7
   发现关系: 7  
   成功率: 100.0%

🌐 Graphs API: implemented
   节点数: 5
   边数: 7
```

## 🔍 故障排查

### 常见问题

1. **服务连接失败**
   ```bash
   # 检查服务状态
   sudo docker compose ps
   
   # 查看服务日志
   sudo docker compose logs paper_parser_backend
   sudo docker compose logs celery_worker
   ```

2. **Neo4j连接问题**
   ```bash
   # 检查Neo4j服务
   sudo docker compose logs neo4j
   
   # 进入Neo4j浏览器
   # 访问 http://localhost:7474
   # 用户名: neo4j, 密码: password123
   ```

3. **引用关系未建立**
   - 检查Celery worker是否正常运行
   - 检查GROBID服务是否可用
   - 查看worker日志中的引用解析过程

4. **测试超时**
   ```bash
   # 增加超时时间
   python test_end_to_end_citation_system.py --mode full --timeout 600
   ```

### 日志查看

```bash
# 查看后端服务日志
sudo docker compose logs -f paper_parser_backend

# 查看Worker日志
sudo docker compose logs -f celery_worker  

# 查看特定任务日志
sudo docker compose exec paper_parser_backend celery -A literature_parser_backend.worker.tasks events
```

## 📝 测试结果文件

测试完成后会生成以下文件：

- `test_results.json` - 详细的测试结果数据
- 控制台输出包含完整的测试报告

## 🔧 高级测试选项

### 自定义测试论文

可以修改 `test_end_to_end_citation_system.py` 中的 `get_test_papers()` 方法来测试其他论文集合。

### 调整匹配阈值

在测试脚本中修改以下参数来测试不同的匹配精度：

```python
# 在 query_neo4j_relationships 方法中
params={"lids": lid, "max_depth": 2, "min_confidence": 0.3}
```

### 测试大规模数据

创建包含更多论文的测试集来验证系统在大规模数据下的性能。

## 🎯 成功标准

一个完全成功的测试应该满足：

1. ✅ 所有文献成功添加到系统
2. ✅ 引用关系解析成功率 > 80%
3. ✅ Graphs API返回正确的图数据
4. ✅ Neo4j中存储了正确的关系数据
5. ✅ 测试总耗时 < 5分钟

---

## 🆘 获取帮助

如果测试遇到问题：

1. 检查所有Docker服务是否正常运行
2. 查看相关服务日志
3. 验证数据库连接
4. 确认API端点可访问

测试成功完成表明你的引用关系系统已经完全就绪！🎉
