#!/usr/bin/env python3
"""
一次性脚本：删除MongoDB中的旧索引
"""
from pymongo import MongoClient


def drop_indexes():
    """连接到MongoDB并删除旧的索引"""
    try:
        # 使用认证信息连接MongoDB
        client = MongoClient(
            "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/literature_parser?authSource=admin"
        )
        db = client["literature_parser"]
        collection = db["literatures"]

        print("准备删除索引...")

        # 删除可能存在的旧索引
        try:
            collection.drop_index("doi_index")
            print("✅ 成功删除 'doi_index'")
        except Exception as e:
            print(f"ℹ️  'doi_index' 不存在或删除失败: {e}")

        try:
            collection.drop_index("arxiv_id_index")
            print("✅ 成功删除 'arxiv_id_index'")
        except Exception as e:
            print(f"ℹ️  'arxiv_id_index' 不存在或删除失败: {e}")

        print("\n索引删除完成。")

    except Exception as e:
        print(f"❌ 连接到MongoDB或执行操作时出错: {e}")
    finally:
        if "client" in locals() and client:
            client.close()


if __name__ == "__main__":
    drop_indexes()
