# literature_parser_backend

This project was generated using fastapi_template.

## Poetry

This project uses poetry. It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
poetry install
poetry run python -m literature_parser_backend
```

This will start the server on the configured host.

You can find swagger documentation at `/api/docs`.

You can read more about poetry here: https://python-poetry.org/

## Docker

You can start the project with docker using this command:

```bash
docker-compose up --build
```

If you want to develop in docker with autoreload and exposed ports add `-f deploy/docker-compose.dev.yml` to your docker command.
Like this:

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```

This command exposes the web application on port 8000, mounts current directory and enables autoreload.

But you have to rebuild image every time you modify `poetry.lock` or `pyproject.toml` with this command:

```bash
docker-compose build
```

## Project structure

```bash
$ tree "literature_parser_backend"
literature_parser_backend
├── conftest.py  # Fixtures for all tests.
├── db  # module contains db configurations
│   ├── dao  # Data Access Objects. Contains different classes to interact with database.
│   └── models  # Package contains different models for ORMs.
├── __main__.py  # Startup script. Starts uvicorn.
├── services  # Package for different external services such as rabbit or redis etc.
├── settings.py  # Main configuration settings for project.
├── static  # Static content.
├── tests  # Tests for project.
└── web  # Package contains web server. Handlers, startup config.
    ├── api  # Package with all handlers.
    │   └── router.py  # Main router.
    ├── application.py  # FastAPI application configuration.
    └── lifespan.py  # Contains actions to perform on startup and shutdown.
```

## Configuration

This application can be configured with environment variables.

You can create `.env` file in the root directory and place all
environment variables here. 

All environment variables should start with "LITERATURE_PARSER_BACKEND_" prefix.

For example if you see in your "literature_parser_backend/settings.py" a variable named like
`random_parameter`, you should provide the "LITERATURE_PARSER_BACKEND_RANDOM_PARAMETER" 
variable to configure the value. This behaviour can be changed by overriding `env_prefix` property
in `literature_parser_backend.settings.Settings.Config`.

An example of .env file:
```bash
LITERATURE_PARSER_BACKEND_RELOAD="True"
LITERATURE_PARSER_BACKEND_PORT="8000"
LITERATURE_PARSER_BACKEND_ENVIRONMENT="dev"
```

You can read more about BaseSettings class here: https://pydantic-docs.helpmanual.io/usage/settings/

## Pre-commit

To install pre-commit simply run inside the shell:
```bash
pre-commit install
```

pre-commit is very useful to check your code before publishing it.
It's configured using .pre-commit-config.yaml file.

By default it runs:
* black (formats your code);
* mypy (validates types);
* ruff (spots possible bugs);


You can read more about pre-commit here: https://pre-commit.com/


## Running tests

If you want to run it in docker, simply run:

```bash
docker-compose run --build --rm api pytest -vv .
docker-compose down
```

For running tests on your local machine.
1. you need to start a database.

I prefer doing it with docker:
```
```


2. Run the pytest.
```bash
pytest -vv .
```

## 🆕 新功能特性 (2025年更新)

### 🧠 业务逻辑去重系统

采用完全业务逻辑去重的方案，移除数据库唯一约束，通过智能瀑布流策略确保数据一致性。

**核心特性**:
- ✅ 异步处理，API立即响应
- ✅ 四阶段瀑布流去重策略
- ✅ 支持高并发提交
- ✅ 智能跨标识符去重

**测试验证**:
```bash
# 运行去重功能测试
python3 test_business_logic_deduplication.py

# 优化数据库索引
python scripts/optimize_business_logic_indexes.py
```

详细文档: [业务逻辑去重指南](BUSINESS_LOGIC_DEDUPLICATION_GUIDE.md)

### 📁 腾讯云COS文件上传

现代化的前端直传文件上传方案，通过预签名URL实现安全、高效的PDF上传。

**核心特性**:
- ✅ 前端直传，减少服务器负载
- ✅ 预签名URL，安全可控
- ✅ 多层安全验证
- ✅ 智能文件下载和处理

**API端点**:
- `POST /api/upload/request-url` - 请求预签名上传URL
- `GET /api/upload/status` - 查询文件上传状态
- `DELETE /api/upload/file` - 删除上传的文件

**测试验证**:
```bash
# 运行完整的上传集成测试
python3 test_cos_upload_integration.py
```

详细文档: [COS上传API指南](COS_UPLOAD_API_GUIDE.md)

### 🔧 配置要求

在 `.env` 文件中添加以下配置:

```bash
# 腾讯云COS配置
LITERATURE_PARSER_BACKEND_COS_SECRET_ID=your_secret_id
LITERATURE_PARSER_BACKEND_COS_SECRET_KEY=your_secret_key
LITERATURE_PARSER_BACKEND_COS_REGION=ap-shanghai
LITERATURE_PARSER_BACKEND_COS_BUCKET=paperparser-1330571283
LITERATURE_PARSER_BACKEND_COS_DOMAIN=paperparser-1330571283.cos.ap-shanghai.myqcloud.com
```

### 📚 完整文档

- [项目结构详解](Project%20Structrue.md)
- [业务逻辑去重指南](BUSINESS_LOGIC_DEDUPLICATION_GUIDE.md)
- [COS上传API指南](COS_UPLOAD_API_GUIDE.md)
