#!/usr/bin/env python3
"""测试references数据"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "literature_parser_backend"))

from db.mongodb import get_mongodb_client
from services.semantic_scholar import SemanticScholarClient
from worker.references_fetcher import ReferencesFetcher


async def test_references():
    """测试references数据"""
    print("=== 检查数据库中的references数据 ===")

    try:
        # 连接数据库
        client = get_mongodb_client()
        db = client["literature_parser"]
        collection = db["literatures"]

        # 查找最近的文献记录
        docs = list(collection.find().sort("created_at", -1).limit(3))
        print(f"找到 {len(docs)} 个最近的文献记录")

        for i, doc in enumerate(docs, 1):
            print(f"\n--- 文献 {i} ---")
            print(f"ID: {doc.get('_id')}")
            title = doc.get("metadata", {}).get("title", "N/A")
            print(f"标题: {title}")
            print(f"创建时间: {doc.get('created_at')}")

            refs = doc.get("references", [])
            print(f"References数量: {len(refs)}")

            if refs:
                print("References详情:")
                for j, ref in enumerate(refs[:2], 1):  # 只显示前2个
                    raw_text = ref.get("raw_text", "N/A")
                    if len(raw_text) > 80:
                        raw_text = raw_text[:80] + "..."
                    print(f"  {j}. Raw: {raw_text}")
                    print(f"     Source: {ref.get('source', 'N/A')}")
                    print(f"     Parsed: {bool(ref.get('parsed'))}")
                    if ref.get("parsed"):
                        parsed = ref.get("parsed")
                        print(f"     -> Title: {parsed.get('title', 'N/A')}")
                        print(f"     -> Year: {parsed.get('year', 'N/A')}")
                if len(refs) > 2:
                    print(f"  ... 还有 {len(refs) - 2} 个references")
            else:
                print("没有references数据")

        # 统计信息
        total_count = collection.count_documents({})
        with_refs_count = collection.count_documents(
            {"references": {"$exists": True, "$not": {"$size": 0}}}
        )
        print(f"\n=== 统计信息 ===")
        print(f"总文献数量: {total_count}")
        print(f"有references的文献数量: {with_refs_count}")
        if total_count > 0:
            print(f"有references的比例: {with_refs_count/total_count*100:.1f}%")

    except Exception as e:
        print(f"数据库检查错误: {e}")
        import traceback

        traceback.print_exc()

    print("\n=== 测试Semantic Scholar API ===")
    try:
        # 测试Semantic Scholar API
        client = SemanticScholarClient()

        # 使用一个已知的DOI测试
        test_doi = "10.48550/arXiv.1706.03762"  # Attention is All You Need
        print(f"测试DOI: {test_doi}")

        refs = client.get_references(test_doi, limit=5)
        print(f"API返回的references数量: {len(refs)}")

        if refs:
            print("API返回的references示例:")
            for i, ref in enumerate(refs[:2], 1):
                print(f"  {i}. Title: {ref.get('title', 'N/A')}")
                print(f"     Year: {ref.get('year', 'N/A')}")
                print(
                    f"     Authors: {[a.get('name', 'N/A') for a in ref.get('authors', [])]}"
                )

    except Exception as e:
        print(f"API测试错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_references())
