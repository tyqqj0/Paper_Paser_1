import enum
from pathlib import Path
from tempfile import gettempdir

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
    # Variables for the database
    db_host: str = "localhost"
    db_port: int = 27017
    db_user: str = "literature_parser_backend"
    db_pass: str = "literature_parser_backend"
    db_base: str = "admin"
    db_echo: bool = False

    # External API settings
    grobid_base_url: str = "http://localhost:8070"
    crossref_api_base_url: str = "https://api.crossref.org"
    semantic_scholar_api_base_url: str = "https://api.semanticscholar.org"

    # API keys and credentials
    crossref_mailto: str = "your-email@example.com"  # Required for CrossRef polite pool
    semantic_scholar_api_key: str = ""  # Optional but recommended

    # Request timeouts and rate limiting
    external_api_timeout: int = 30
    external_api_max_retries: int = 3

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
    celery_task_track_started: bool = True
    celery_task_time_limit: int = 30 * 60  # 30 minutes
    celery_task_soft_time_limit: int = 25 * 60  # 25 minutes
    celery_worker_prefetch_multiplier: int = 1

    @property
    def db_url(self) -> URL:
        """
        Assemble database URL from settings.

        :return: database URL.
        """
        return URL.build(
            scheme="mongodb",
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            password=self.db_pass,
            path=f"/{self.db_base}",
        )

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LITERATURE_PARSER_BACKEND_",
        env_file_encoding="utf-8",
    )


settings = Settings()
