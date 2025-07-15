# MongoDB Compass 连接指南

## 📊 连接到Docker中的MongoDB

您的MongoDB是通过Docker容器运行的，可以使用MongoDB Compass来图形化管理。

### 🔗 连接信息

**连接URI**：
```
mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin
```

**或者分别填写**：
- **主机名**: `localhost`
- **端口**: `27017`
- **数据库**: `admin`
- **用户名**: `literature_parser_backend`
- **密码**: `literature_parser_backend`
- **认证数据库**: `admin`

### 📋 连接步骤

1. **启动Docker服务**：
   ```bash
   docker-compose up -d
   ```

2. **确认MongoDB容器运行**：
   ```bash
   docker ps | findstr mongo
   ```

3. **打开MongoDB Compass**

4. **新建连接**：
   - 点击 "New Connection"
   - 粘贴连接URI，或者手动填写连接信息
   - 点击 "Connect"

### 🗂️ 数据库结构

连接成功后，您会看到：

```
📁 admin (认证数据库)
📁 literature_parser (主要数据库)
  └── 📄 literatures (文献集合)
      ├── 文献元数据
      ├── 解析内容
      ├── 参考文献
      └── 任务信息
```

### 🔍 查看数据

在 `literature_parser` 数据库的 `literatures` 集合中，您可以看到：

- **文献记录**：每个处理过的文献
- **DOI、ArXiv ID**：标识符信息
- **标题、作者**：元数据
- **解析状态**：任务进度
- **参考文献**：提取的引用信息

### 📝 示例查询

在Compass中，您可以使用这些查询：

```javascript
// 查找所有文献
{}

// 根据DOI查找
{"identifiers.doi": "10.1038/nature12373"}

// 根据标题查找
{"metadata.title": /test/i}

// 查找最近的文献
{}, {sort: {"created_at": -1}}
```

### 🛠️ 故障排除

如果连接失败：

1. **检查Docker容器状态**：
   ```bash
   docker logs literature_parser_backend-db-1
   ```

2. **检查端口占用**：
   ```bash
   netstat -an | findstr 27017
   ```

3. **重启MongoDB容器**：
   ```bash
   docker-compose restart db
   ```

### 🎯 使用建议

- **实时监控**：在运行测试时打开Compass，可以实时看到数据写入
- **数据验证**：验证API创建的文献记录是否正确
- **调试工具**：查看任务状态和错误信息
- **性能监控**：观察查询性能和索引使用情况

---

💡 **提示**：第一次连接可能需要等待几秒钟，因为MongoDB容器需要完全启动。 