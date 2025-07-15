#!/usr/bin/env python3
"""
检查所有服务是否正常运行
"""
import asyncio

import httpx
import redis
from pymongo import MongoClient

from literature_parser_backend.settings import Settings


async def check_api_health():
    """检查 API 健康状态"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/health", timeout=10)
            if response.status_code == 200:
                print("✅ API 服务正常")
                return True
            else:
                print(f"❌ API 服务异常: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ API 服务连接失败: {e}")
        return False


def check_redis_connection():
    """检查 Redis 连接"""
    try:
        settings = Settings()
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            socket_timeout=5,
        )
        r.ping()
        print("✅ Redis 连接正常")
        return True
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False


def check_mongodb_connection():
    """检查 MongoDB 连接"""
    try:
        settings = Settings()
        client = MongoClient(
            host=settings.db_host,
            port=settings.db_port,
            username=settings.db_user,
            password=settings.db_pass,
            authSource=settings.db_base,
            serverSelectionTimeoutMS=5000,
        )
        # 尝试连接
        client.admin.command("ping")
        print("✅ MongoDB 连接正常")
        return True
    except Exception as e:
        print(f"❌ MongoDB 连接失败: {e}")
        return False


async def check_grobid_service():
    """检查 GROBID 服务"""
    try:
        settings = Settings()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.grobid_base_url}/api/isalive",
                timeout=10,
            )
            if response.status_code == 200:
                print("✅ GROBID 服务正常")
                return True
            else:
                print(f"❌ GROBID 服务异常: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ GROBID 服务连接失败: {e}")
        return False


async def main():
    """主函数"""
    print("🔍 检查服务状态...")
    print("=" * 40)

    # 检查各项服务
    results = []

    print("\n📡 检查 API 服务...")
    results.append(await check_api_health())

    print("\n📊 检查 Redis 连接...")
    results.append(check_redis_connection())

    print("\n🗄️ 检查 MongoDB 连接...")
    results.append(check_mongodb_connection())

    print("\n📄 检查 GROBID 服务...")
    results.append(await check_grobid_service())

    # 总结
    print("\n" + "=" * 40)
    success_count = sum(results)
    total_count = len(results)

    if success_count == total_count:
        print("🎉 所有服务运行正常！")
        print("✅ 系统已就绪，可以开始处理文献任务")
    else:
        print(f"⚠️  {success_count}/{total_count} 个服务正常")
        print("❌ 请检查失败的服务并重新启动")

    return success_count == total_count


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
