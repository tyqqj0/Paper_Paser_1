import enum
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Dict

from pydantic_settings import BaseSettings, SettingsConfigDict
from yarl import URL

TEMP_DIR = Path(gettempdir())


class LogLevel(str, enum.Enum):
    """Possible log levels."""

    NOTSET = "NOTSET"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FATAL = "FATAL"


# DatabaseMode enum removed - using Neo4j only


class Settings(BaseSettings):
    """
    Application settings.

    These parameters can be configured
    with environment variables.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    # quantity of workers for uvicorn
    workers_count: int = 1
    # Enable uvicorn reloading
    reload: bool = False

    # Current environment
    environment: str = "dev"

    log_level: LogLevel = LogLevel.INFO

    # CORS settings
    cors_origins: list[str] = ["*"]  # 允许的源，生产环境应该设置具体域名
    cors_methods: list[str] = ["*"]  # 允许的HTTP方法
    cors_headers: list[str] = ["*"]  # 允许的请求头
    cors_credentials: bool = True    # 是否允许携带凭证
    # ========== Database Configuration ==========
    # Neo4j settings (primary database)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "literature_parser_neo4j"
    neo4j_database: str = "neo4j"  # Default database name
    
    # Elasticsearch settings (for full-text search)
    es_host: str = "localhost"
    es_port: int = 9200
    es_username: str = "elastic"
    es_password: str = "literature_parser_elastic"
    es_index_prefix: str = "literature_parser"

    # External API settings
    grobid_base_url: str = "http://localhost:8070"
    crossref_api_base_url: str = "https://api.crossref.org"
    semantic_scholar_api_base_url: str = "https://api.semanticscholar.org"

    # API keys and credentials
    crossref_mailto: str = "your-email@example.com"  # Required for CrossRef polite pool
    semantic_scholar_api_key: str = ""  # Optional but recommended

    # Request timeouts and rate limiting
    external_api_timeout: int = 40  # 调整为40秒
    external_api_max_retries: int = 3

    # Proxy settings
    http_proxy: str = ""
    https_proxy: str = ""

    # Redis settings for Celery
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # Celery settings
    celery_broker_url: str = ""  # Will be computed from redis settings
    celery_result_backend: str = ""  # Will be computed from redis settings
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: list[str] = ["json"]
    celery_timezone: str = "UTC"
    celery_enable_utc: bool = True

    # 腾讯云COS对象存储设置
    cos_secret_id: str = ""  # 腾讯云SecretId
    cos_secret_key: str = ""  # 腾讯云SecretKey
    cos_region: str = "ap-shanghai"  # COS区域
    cos_bucket: str = "paperparser-1330571283"  # COS存储桶名称
    cos_domain: str = "paperparser-1330571283.cos.ap-shanghai.myqcloud.com"  # COS域名

    # 文件上传设置
    upload_max_file_size: int = 50 * 1024 * 1024  # 50MB
    upload_allowed_extensions: list[str] = [".pdf"]  # 允许的文件扩展名
    upload_presigned_url_expires: int = 3600  # 预签名URL过期时间(秒)，默认1小时
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 35 * 60  # 35 minutes (增加5分钟缓冲)
    celery_task_soft_time_limit: int = 30 * 60  # 30 minutes (增加5分钟缓冲)
    celery_worker_prefetch_multiplier: int = 2  # 每个worker预取2个任务提高效率

    # MongoDB db_url method removed - using Neo4j only

    @property
    def redis_url(self) -> str:
        """
        Assemble Redis URL from settings.

        :return: Redis URL for Celery broker and result backend.
        """
        auth_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url_computed(self) -> str:
        """Get Celery broker URL, using redis_url if not explicitly set."""
        return self.celery_broker_url or self.redis_url

    @property
    def celery_result_backend_computed(self) -> str:
        """Get Celery result backend URL, using redis_url if not explicitly set."""
        return self.celery_result_backend or self.redis_url
    
    @property
    def neo4j_connection_config(self) -> Dict[str, str]:
        """Get Neo4j connection configuration."""
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password,
            "database": self.neo4j_database
        }

    def get_proxy_dict(self) -> Dict[str, str]:
        """Get proxy configuration as dictionary for requests."""
        proxy_dict = {}
        if self.http_proxy:
            proxy_dict["http"] = self.http_proxy
        if self.https_proxy:
            proxy_dict["https"] = self.https_proxy
        return proxy_dict

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LITERATURE_PARSER_BACKEND_",
        env_file_encoding="utf-8",
    )


settings = Settings()
