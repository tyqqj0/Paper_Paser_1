#!/usr/bin/env python3
"""
查找已完成的任务，用于测试任务持久化机制
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from literature_parser_backend.settings import Settings


async def find_completed_tasks():
    """查找已完成的任务"""
    settings = Settings()
    
    # 连接数据库
    client = AsyncIOMotorClient(str(settings.db_url))
    db = client.get_database()
    collection = db.literatures
    
    try:
        # 查找有task_info且状态为success的文献
        cursor = collection.find(
            {
                "task_info.task_id": {"$exists": True},
                "task_info.status": {"$in": ["success", "partial_success"]}
            },
            {
                "_id": 1,
                "task_info.task_id": 1,
                "task_info.status": 1,
                "task_info.completed_at": 1,
                "metadata.title": 1
            }
        ).sort("task_info.completed_at", -1).limit(5)
        
        completed_tasks = []
        async for doc in cursor:
            completed_tasks.append({
                "literature_id": str(doc["_id"]),
                "task_id": doc.get("task_info", {}).get("task_id"),
                "status": doc.get("task_info", {}).get("status"),
                "completed_at": doc.get("task_info", {}).get("completed_at"),
                "title": doc.get("metadata", {}).get("title", "N/A")
            })
        
        print("🔍 找到的已完成任务:")
        print("=" * 80)
        
        if not completed_tasks:
            print("❌ 未找到已完成的任务")
            return None
        
        for i, task in enumerate(completed_tasks, 1):
            print(f"{i}. Task ID: {task['task_id']}")
            print(f"   Literature ID: {task['literature_id']}")
            print(f"   Status: {task['status']}")
            print(f"   Title: {task['title'][:60]}...")
            print(f"   Completed: {task['completed_at']}")
            print("-" * 80)
        
        return completed_tasks[0]["task_id"] if completed_tasks else None
        
    except Exception as e:
        print(f"❌ 查询异常: {e}")
        return None
    finally:
        client.close()


async def main():
    task_id = await find_completed_tasks()
    if task_id:
        print(f"\n✅ 可用于测试的Task ID: {task_id}")
    else:
        print("\n❌ 未找到可用的已完成任务")


if __name__ == "__main__":
    asyncio.run(main())
