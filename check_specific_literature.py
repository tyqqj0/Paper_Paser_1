#!/usr/bin/env python3
"""
检查特定文献记录的详细信息
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId


async def check_literature_details():
    """检查特定文献记录的详细信息"""
    # 连接MongoDB，使用正确的认证
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017"
    )
    db = client.literature_parser
    collection = db.literatures

    # 检查特定文献ID
    literature_id = "68786dc80afb52143bbc737b"

    try:
        # 转换为ObjectId
        obj_id = ObjectId(literature_id)
        doc = await collection.find_one({"_id": obj_id})

        if doc:
            print(f"✅ 找到文献记录: {literature_id}")
            print(f"任务ID: {doc.get('task_info', {}).get('task_id')}")
            print(f"创建时间: {doc.get('task_info', {}).get('created_at')}")

            # 检查标识符
            identifiers = doc.get("identifiers", {})
            print(f"DOI: {identifiers.get('doi')}")
            print(f"ArXiv ID: {identifiers.get('arxiv_id')}")
            print(f"指纹: {identifiers.get('fingerprint')}")

            # 检查元数据
            metadata = doc.get("metadata", {})
            print(f"标题: {metadata.get('title')}")
            print(f"作者: {metadata.get('authors')}")
            print(f"年份: {metadata.get('year')}")
            print(f"期刊: {metadata.get('journal')}")
            print(f"摘要: {metadata.get('abstract', '')[:100]}...")

            # 检查内容
            content = doc.get("content", {})
            print(f"PDF URL: {content.get('pdf_url')}")
            print(f"内容来源: {content.get('sources_tried')}")

            # 检查引用
            references = doc.get("references", {})
            if references:
                print(f"引用数量: {len(references.get('references', []))}")

        else:
            print(f"❌ 未找到文献记录: {literature_id}")

            # 检查所有记录
            print("\n检查所有记录...")
            async for doc in collection.find({}).limit(5):
                print(f"记录ID: {doc.get('_id')}")
                print(f"任务ID: {doc.get('task_info', {}).get('task_id')}")
                print(f"标题: {doc.get('metadata', {}).get('title')}")
                print("---")

    except Exception as e:
        print(f"❌ 检查失败: {e}")

    client.close()


if __name__ == "__main__":
    asyncio.run(check_literature_details())
