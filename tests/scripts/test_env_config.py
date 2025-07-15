#!/usr/bin/env python3
"""
测试环境变量配置
"""
import os

from literature_parser_backend.settings import Settings


def test_env_config():
    """测试环境变量配置"""
    print("🔍 测试环境变量配置...")
    print("=" * 50)

    # 创建设置实例
    settings = Settings()

    # 打印数据库配置
    print("📊 数据库配置:")
    print(f"  DB Host: {settings.db_host}")
    print(f"  DB Port: {settings.db_port}")
    print(f"  DB User: {settings.db_user}")
    print(f"  DB Pass: {settings.db_pass}")
    print(f"  DB Base: {settings.db_base}")
    print(f"  DB URL: {settings.db_url}")

    print("\n🔗 Redis 配置:")
    print(f"  Redis Host: {settings.redis_host}")
    print(f"  Redis Port: {settings.redis_port}")
    print(f"  Redis DB: {settings.redis_db}")
    print(f"  Redis URL: {settings.redis_url}")

    print("\n⚡ Celery 配置:")
    print(f"  Broker URL: {settings.celery_broker_url_computed}")
    print(f"  Result Backend: {settings.celery_result_backend_computed}")

    print("\n🌐 外部服务配置:")
    print(f"  GROBID URL: {settings.grobid_base_url}")
    print(f"  CrossRef Email: {settings.crossref_mailto}")

    print("\n📱 应用配置:")
    print(f"  Host: {settings.host}")
    print(f"  Port: {settings.port}")
    print(f"  Log Level: {settings.log_level}")

    print("\n🔑 环境变量检查:")
    env_vars = [
        "LITERATURE_PARSER_BACKEND_DB_HOST",
        "LITERATURE_PARSER_BACKEND_DB_PORT",
        "LITERATURE_PARSER_BACKEND_DB_USER",
        "LITERATURE_PARSER_BACKEND_DB_PASS",
        "LITERATURE_PARSER_BACKEND_DB_BASE",
        "LITERATURE_PARSER_BACKEND_REDIS_HOST",
        "LITERATURE_PARSER_BACKEND_REDIS_PORT",
        "LITERATURE_PARSER_BACKEND_CELERY_BROKER_URL",
        "LITERATURE_PARSER_BACKEND_CELERY_RESULT_BACKEND",
    ]

    for var in env_vars:
        value = os.getenv(var, "未设置")
        print(f"  {var}: {value}")

    print("\n✅ 环境变量配置测试完成")


if __name__ == "__main__":
    test_env_config()
