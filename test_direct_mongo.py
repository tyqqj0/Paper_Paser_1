#!/usr/bin/env python3
"""
直接测试MongoDB连接
"""

from pymongo import MongoClient
from bson import ObjectId


def test_direct_mongo():
    """直接测试MongoDB连接"""

    # 使用与worker相同的连接配置
    client = MongoClient(
        host="localhost",
        port=27017,
        username="literature_parser_backend",
        password="literature_parser_backend",
        authSource="admin",
        serverSelectionTimeoutMS=5000,
    )

    try:
        # 连接到数据库
        db = client["literature_parser"]
        collection = db["literatures"]

        # 查询最新的文献
        print("🔍 查询最新的文献...")
        latest_docs = list(collection.find().sort("_id", -1).limit(3))

        for doc in latest_docs:
            print(f"ID: {doc['_id']}")
            print(f"标题: {doc.get('metadata', {}).get('title', 'N/A')}")
            print(f"参考文献数量: {len(doc.get('references', []))}")
            if doc.get("references"):
                print(
                    f"第一个参考文献来源: {doc['references'][0].get('source', 'N/A')}"
                )
            print("---")

        # 查询特定ID的文献
        specific_id = "6875e3608c887aef3485f196"
        print(f"\n🔍 查询特定ID的文献: {specific_id}")

        try:
            doc = collection.find_one({"_id": ObjectId(specific_id)})
            if doc:
                print("✅ 找到文献!")
                print(f"标题: {doc.get('metadata', {}).get('title', 'N/A')}")
                references = doc.get("references", [])
                print(f"参考文献数量: {len(references)}")
                if references:
                    print(f"第一个参考文献来源: {references[0].get('source', 'N/A')}")
                    print(
                        f"第一个参考文献标题: {references[0].get('parsed', {}).get('title', 'N/A')[:60]}..."
                    )
            else:
                print("❌ 未找到文献")
        except Exception as e:
            print(f"❌ 查询特定文献时出错: {e}")

    except Exception as e:
        print(f"❌ 连接MongoDB时出错: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    test_direct_mongo()
