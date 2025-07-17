#!/usr/bin/env python3
"""
检查数据库中最新的文献记录状态
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json
from datetime import datetime


async def check_latest_records():
    """检查最新的文献记录"""
    try:
        client = AsyncIOMotorClient(
            "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017"
        )
        db = client.literature_parser
        collection = db.literature

        # 首先检查总记录数
        total_count = await collection.count_documents({})
        print(f"数据库中总记录数: {total_count}")

        if total_count == 0:
            print("数据库中没有文献记录")
            return

        # 获取最新的3条记录
        cursor = collection.find().sort("created_at", -1).limit(3)
        records = await cursor.to_list(length=3)

        print("=" * 60)
        print("最新的3条文献记录:")
        print("=" * 60)

        for i, record in enumerate(records, 1):
            print(f"\n记录 {i}:")
            print(f"ID: {record['_id']}")
            print(f"标题: {record.get('metadata', {}).get('title', 'N/A')}")
            print(f"任务ID: {record.get('task_info', {}).get('task_id', 'N/A')}")
            print(f"任务状态: {record.get('task_info', {}).get('status', 'N/A')}")
            print(
                f"组件状态: {record.get('task_info', {}).get('component_status', 'N/A')}"
            )
            print(f"创建时间: {record.get('created_at', 'N/A')}")
            print(f"更新时间: {record.get('updated_at', 'N/A')}")
            print(f"标识符: {record.get('identifiers', {})}")
            print(
                f"GROBID状态: {record.get('content', {}).get('grobid_processing_info', {}).get('status', 'N/A')}"
            )
            print("-" * 40)

    except Exception as e:
        print(f"检查数据库时出错: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(check_latest_records())
