#!/usr/bin/env python3
"""检查现有文献数据的实际结构"""

import asyncio

import motor.motor_asyncio
from bson import ObjectId


async def main():
    # 连接数据库
    client = motor.motor_asyncio.AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin",
    )
    db = client.admin

    try:
        # 首先检查所有集合
        collections = await db.list_collection_names()
        print(f"数据库集合: {collections}")

        # 尝试不同的集合名称
        collection_names = ["literature", "literatures"]
        doc = None

        for coll_name in collection_names:
            if coll_name in collections:
                print(f"尝试从集合 {coll_name} 查找文献...")
                doc = await db[coll_name].find_one(
                    {"_id": ObjectId("68760017cce9ba724afaeb57")},
                )
                if doc:
                    print(f"✅ 在集合 {coll_name} 中找到文献")
                    break
                else:
                    # 查看该集合中有什么文档
                    count = await db[coll_name].count_documents({})
                    print(f"集合 {coll_name} 包含 {count} 个文档")
                    if count > 0:
                        sample = await db[coll_name].find({}).limit(1).to_list(1)
                        if sample:
                            print(f"示例文档ID: {sample[0].get('_id')}")

        if doc:
            print("🔍 文献数据结构分析:")
            print("=" * 50)

            # 基本信息
            print(f"标题: {doc.get('title', 'N/A')}")
            print(f"DOI: {doc.get('doi', 'N/A')}")
            print(f"作者数量: {len(doc.get('authors', []))}")
            print(f"年份: {doc.get('year', 'N/A')}")
            print(f"期刊: {doc.get('journal', 'N/A')}")

            # 检查identifiers结构
            identifiers = doc.get("identifiers", {})
            print("\n🆔 标识符信息:")
            print(f"   DOI: {identifiers.get('doi', 'N/A')}")
            print(f"   ArXiv: {identifiers.get('arxiv_id', 'N/A')}")
            print(f"   PMID: {identifiers.get('pmid', 'N/A')}")

            # 检查metadata结构
            metadata = doc.get("metadata", {})
            print("\n📊 元数据来源:")
            print(f"   CrossRef: {'✅' if metadata.get('crossref') else '❌'}")
            print(
                f"   Semantic Scholar: {'✅' if metadata.get('semantic_scholar') else '❌'}",
            )
            print(f"   GROBID: {'✅' if metadata.get('grobid') else '❌'}")

            # 检查具体元数据内容
            if metadata.get("crossref"):
                crossref_data = metadata["crossref"]
                print(f"   CrossRef标题: {crossref_data.get('title', 'N/A')}")
                print(f"   CrossRef作者: {len(crossref_data.get('author', []))}")

            if metadata.get("semantic_scholar"):
                ss_data = metadata["semantic_scholar"]
                print(f"   Semantic Scholar标题: {ss_data.get('title', 'N/A')}")
                print(f"   Semantic Scholar作者: {len(ss_data.get('authors', []))}")

            # 检查references
            references = doc.get("references", [])
            print(f"\n📚 参考文献: {len(references)} 篇")
            if references:
                print(f"   第一篇: {references[0].get('title', 'N/A')[:50]}...")
                print(f"   来源: {references[0].get('source', 'N/A')}")

            # 检查content
            content = doc.get("content", {})
            print("\n📄 内容信息:")
            print(f"   PDF URL: {content.get('pdf_url', 'N/A')}")
            print(f"   下载状态: {content.get('status', 'N/A')}")
            print(f"   全文长度: {len(content.get('full_text', ''))}")

            # 检查文档顶级字段结构
            print("\n🗂️ 文档顶级字段:")
            for key in sorted(doc.keys()):
                if key != "_id":
                    value = doc[key]
                    if isinstance(value, dict):
                        print(f"   {key}: dict({len(value)} keys)")
                    elif isinstance(value, list):
                        print(f"   {key}: list({len(value)} items)")
                    else:
                        print(f"   {key}: {type(value).__name__}")

        else:
            print("❌ 未找到指定文献")

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
