#!/usr/bin/env python3
"""
修复数据库索引问题
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


async def fix_database_indexes():
    """修复MongoDB索引问题"""
    print("🔧 修复MongoDB索引问题...")

    # 连接数据库
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. 查看现有索引
        print("📋 检查现有索引...")
        indexes = await collection.list_indexes().to_list(length=None)
        for index in indexes:
            print(f"   索引: {index['name']}")
            if "key" in index:
                print(f"   键: {index['key']}")
            if "unique" in index:
                print(f"   唯一: {index['unique']}")
            print()

        # 2. 删除有问题的fingerprint唯一索引
        print("🗑️ 删除有问题的fingerprint唯一索引...")
        try:
            await collection.drop_index("fingerprint_unique_index")
            print("   ✅ fingerprint_unique_index 索引已删除")
        except Exception as e:
            print(f"   ⚠️ 删除索引失败或索引不存在: {e}")

        # 3. 创建新的部分索引（允许null值但不重复非null值）
        print("🔨 创建新的部分索引...")
        try:
            await collection.create_index(
                "identifiers.fingerprint",
                unique=True,
                partialFilterExpression={"identifiers.fingerprint": {"$ne": None}},
                name="fingerprint_partial_unique_index",
            )
            print("   ✅ fingerprint_partial_unique_index 索引已创建")
        except Exception as e:
            print(f"   ⚠️ 创建索引失败: {e}")

        # 4. 确保其他必要索引存在
        print("🔨 确保其他索引存在...")
        indexes_to_create = [
            ("identifiers.doi", "doi_index"),
            ("identifiers.arxiv_id", "arxiv_id_index"),
            ("task_info.task_id", "task_id_index"),
        ]

        for field, index_name in indexes_to_create:
            try:
                await collection.create_index(field, name=index_name)
                print(f"   ✅ {index_name} 索引已确保存在")
            except Exception as e:
                print(f"   ⚠️ 创建 {index_name} 索引失败: {e}")

        # 5. 清理任何有问题的文档
        print("🧹 清理有问题的文档...")

        # 查找所有失败状态的文档
        failed_docs = await collection.find({"task_info.status": "failed"}).to_list(
            length=None
        )
        print(f"   找到 {len(failed_docs)} 个失败状态的文档")

        if failed_docs:
            # 删除失败的文档
            result = await collection.delete_many({"task_info.status": "failed"})
            print(f"   ✅ 删除了 {result.deleted_count} 个失败文档")

        # 查找重复的null fingerprint文档
        null_fingerprint_docs = await collection.find(
            {"identifiers.fingerprint": None}
        ).to_list(length=None)
        if len(null_fingerprint_docs) > 1:
            # 保留最新的，删除其他的
            docs_to_delete = null_fingerprint_docs[:-1]  # 除了最后一个
            ids_to_delete = [doc["_id"] for doc in docs_to_delete]
            if ids_to_delete:
                result = await collection.delete_many({"_id": {"$in": ids_to_delete}})
                print(
                    f"   ✅ 删除了 {result.deleted_count} 个重复的null fingerprint文档"
                )

        print("✅ 数据库修复完成！")

    except Exception as e:
        print(f"❌ 修复过程中出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(fix_database_indexes())
