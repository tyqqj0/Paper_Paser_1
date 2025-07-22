# syntax=docker/dockerfile:1

# =================================================================
# 1. "base" 阶段：构建一个包含 Poetry 和所有依赖的通用环境
# =================================================================
FROM python:3.11-slim AS base

# 设置环境变量，避免交互式提示
ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# 设置工作目录
WORKDIR /app

# 先只复制这两个文件，如果它们不变，下面所有的安装步骤都能被缓存！
COPY pyproject.toml poetry.lock ./

# 安装 Poetry 并配置国内源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    # pip install --upgrade pip && \
    pip install poetry==1.8.2

# [修正] 分成两个 RUN 命令
# 第一步：配置 poetry，这是一个快速操作
RUN poetry config installer.parallel false

# [修正] 第二步：安装依赖，并把 --mount 标志正确地用于这个 RUN 指令
# poetry 的缓存目录在不同系统下可能不同，/root/.cache/pypoetry 是一个常见的默认值
RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --no-root


# =================================================================
# 2. "prod" 阶段：构建一个精简的、用于生产的最终镜像
# =================================================================
FROM python:3.11-slim AS prod

# 设置和 base 阶段一样的环境变量
ENV PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# [关键优化] 直接从 "base" 阶段复制已经安装好的依赖库和所有可执行文件
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin/ /usr/local/bin/
COPY --from=base /app/pyproject.toml /app/poetry.lock ./

# [关键优化] 最后才复制你的项目代码
COPY . .

# 暴露端口 (如果你的应用需要)
EXPOSE 8000

# 定义容器启动命令
CMD ["python", "-m", "literature_parser_backend"]


# =================================================================
# 3. "dev" 阶段 (可选): 构建一个用于本地开发的镜像
# =================================================================
FROM base AS dev

WORKDIR /app

# 从 base 阶段复制所有依赖
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /app/pyproject.toml /app/poetry.lock ./

# 复制你的全部代码，并设置为可交互模式
COPY . .
CMD ["tail", "-f", "/dev/null"]
