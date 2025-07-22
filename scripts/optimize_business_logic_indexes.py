#!/usr/bin/env python3
"""
业务逻辑去重索引优化脚本

移除所有唯一约束，创建纯查询性能索引，完全依赖业务逻辑进行去重。
这是实现方案C的关键步骤：数据库索引简化，业务逻辑去重。
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, TEXT
from pymongo.errors import OperationFailure


async def optimize_business_logic_indexes():
    """优化索引以支持纯业务逻辑去重。"""
    print("🚀 开始优化索引以支持业务逻辑去重...")

    # 连接数据库 (使用容器内的服务名)
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@db:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. 分析当前索引状态
        print("\n📋 分析当前索引状态...")
        existing_indexes = await collection.list_indexes().to_list(length=None)

        print("当前索引:")
        unique_indexes = []
        for idx in existing_indexes:
            name = idx.get('name', 'unnamed')
            unique = idx.get('unique', False)
            partial = 'partialFilterExpression' in idx
            
            status = ""
            if unique:
                status += " [UNIQUE]"
                unique_indexes.append(name)
            if partial:
                status += " [PARTIAL]"
                
            print(f"  - {name}: {idx.get('key', {})}{status}")

        # 2. 移除所有唯一约束索引
        print(f"\n🗑️  移除 {len(unique_indexes)} 个唯一约束索引...")
        
        for index_name in unique_indexes:
            if index_name != "_id_":  # 保留MongoDB默认主键索引
                try:
                    await collection.drop_index(index_name)
                    print(f"  ✅ 已移除唯一索引: {index_name}")
                except OperationFailure as e:
                    print(f"  ⚠️  移除索引失败 {index_name}: {e}")

        # 3. 创建纯查询性能索引（无唯一约束）
        print("\n🔨 创建业务逻辑去重查询索引...")

        # 核心标识符查询索引（非唯一）
        core_query_indexes = [
            IndexModel(
                [("identifiers.doi", ASCENDING)],
                name="doi_query_index",
                background=True,
                partialFilterExpression={"identifiers.doi": {"$type": "string"}}
            ),
            IndexModel(
                [("identifiers.arxiv_id", ASCENDING)],
                name="arxiv_query_index",
                background=True,
                partialFilterExpression={"identifiers.arxiv_id": {"$type": "string"}}
            ),
            IndexModel(
                [("identifiers.pmid", ASCENDING)],
                name="pmid_query_index",
                background=True,
                partialFilterExpression={"identifiers.pmid": {"$type": "string"}}
            ),
        ]

        # 内容指纹查询索引（非唯一）
        content_query_indexes = [
            IndexModel(
                [("identifiers.fingerprint", ASCENDING)],
                name="fingerprint_query_index",
                background=True,
                partialFilterExpression={"identifiers.fingerprint": {"$type": "string"}}
            ),
        ]

        # URL查询索引
        url_query_indexes = [
            IndexModel(
                [("identifiers.source_urls", ASCENDING)], 
                name="source_urls_query_index",
                background=True
            ),
            IndexModel(
                [("content.pdf_url", ASCENDING)],
                name="pdf_url_query_index",
                background=True,
                partialFilterExpression={"content.pdf_url": {"$type": "string"}}
            ),
            IndexModel(
                [("content.source_page_url", ASCENDING)],
                name="source_page_url_query_index",
                background=True,
                partialFilterExpression={"content.source_page_url": {"$type": "string"}}
            ),
        ]

        # 任务状态查询索引
        task_query_indexes = [
            IndexModel(
                [("task_info.task_id", ASCENDING)], 
                name="task_id_query_index",
                background=True
            ),
            IndexModel(
                [("task_info.status", ASCENDING)], 
                name="task_status_query_index",
                background=True
            ),
        ]

        # 元数据查询索引
        metadata_query_indexes = [
            IndexModel(
                [("metadata.title", TEXT)], 
                name="title_text_search_index",
                background=True
            ),
            IndexModel(
                [("metadata.title", ASCENDING)], 
                name="title_exact_query_index",
                background=True
            ),
            IndexModel(
                [("metadata.authors.name", ASCENDING)], 
                name="author_name_query_index",
                background=True
            ),
        ]

        # 时间查询索引
        time_query_indexes = [
            IndexModel(
                [("created_at", ASCENDING)], 
                name="created_at_query_index",
                background=True
            ),
            IndexModel(
                [("updated_at", ASCENDING)], 
                name="updated_at_query_index",
                background=True
            ),
        ]

        # 创建所有查询索引
        all_query_indexes = (
            core_query_indexes + 
            content_query_indexes + 
            url_query_indexes + 
            task_query_indexes + 
            metadata_query_indexes + 
            time_query_indexes
        )

        print(f"创建 {len(all_query_indexes)} 个查询性能索引...")

        for index in all_query_indexes:
            try:
                await collection.create_indexes([index])
                print(f"  ✅ 创建查询索引: {index.document.get('name', 'unnamed')}")
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    print(f"  ℹ️  索引已存在: {index.document.get('name', 'unnamed')}")
                else:
                    print(f"  ⚠️  创建索引失败 {index.document.get('name', 'unnamed')}: {e}")

        # 4. 验证最终索引状态
        print("\n🔍 验证最终索引状态...")
        final_indexes = await collection.list_indexes().to_list(length=None)

        unique_count = 0
        query_count = 0
        
        print("最终索引列表:")
        for idx in final_indexes:
            name = idx.get("name", "unnamed")
            unique = idx.get("unique", False)
            partial = "partialFilterExpression" in idx
            
            if unique and name != "_id_":
                unique_count += 1
                status = " [⚠️ UNIQUE]"
            else:
                query_count += 1
                status = " [✅ QUERY]"
                
            if partial:
                status += " [PARTIAL]"
                
            print(f"  • {name}{status}")

        print(f"\n📊 索引统计:")
        print(f"  • 查询索引: {query_count} 个")
        print(f"  • 唯一约束: {unique_count} 个")
        
        if unique_count <= 1:  # 只有_id_索引
            print("  ✅ 成功移除所有业务唯一约束!")
        else:
            print("  ⚠️  仍有业务唯一约束存在")

        print("\n✅ 业务逻辑去重索引优化完成!")
        print("\n📈 优化效果:")
        print("  • 移除数据库层面的唯一约束冲突")
        print("  • 保持高效的查询性能")
        print("  • 完全依赖业务逻辑进行去重")
        print("  • 支持复杂的去重策略和边缘情况处理")

    except Exception as e:
        print(f"❌ 索引优化过程中出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(optimize_business_logic_indexes())
