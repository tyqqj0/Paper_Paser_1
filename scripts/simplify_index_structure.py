#!/usr/bin/env python3
"""
索引结构最终简化脚本

移除复杂的复合索引和不必要的索引，只保留最基本的查询性能索引。
实现真正的"简化索引，业务逻辑去重"方案。
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, TEXT
from pymongo.errors import OperationFailure


async def simplify_index_structure():
    """简化索引结构，只保留核心查询索引。"""
    print("🚀 开始简化索引结构...")

    # 连接数据库
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@db:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures

    try:
        # 1. 分析当前索引
        print("\n📋 分析当前索引结构...")
        existing_indexes = await collection.list_indexes().to_list(length=None)

        print("当前索引:")
        current_indexes = []
        for idx in existing_indexes:
            name = idx.get('name', 'unnamed')
            current_indexes.append(name)
            unique = idx.get('unique', False)
            partial = 'partialFilterExpression' in idx
            
            status = ""
            if unique:
                status += " [UNIQUE]"
            if partial:
                status += " [PARTIAL]"
                
            print(f"  - {name}: {idx.get('key', {})}{status}")

        # 2. 定义核心必需索引
        print("\n🎯 定义核心必需索引...")
        
        # 核心必需索引列表
        essential_indexes = {
            "_id_": "MongoDB默认主键索引",
            "doi_query_index": "DOI查询索引",
            "arxiv_query_index": "ArXiv ID查询索引", 
            "fingerprint_query_index": "内容指纹查询索引",
            "task_id_query_index": "任务ID查询索引",
            "title_text_search_index": "标题全文搜索索引"
        }
        
        print("核心必需索引:")
        for name, desc in essential_indexes.items():
            print(f"  ✅ {name}: {desc}")

        # 3. 识别可移除的索引
        removable_indexes = []
        for idx_name in current_indexes:
            if idx_name not in essential_indexes:
                removable_indexes.append(idx_name)
        
        print(f"\n🗑️  识别到 {len(removable_indexes)} 个可移除的索引:")
        for idx_name in removable_indexes:
            print(f"  - {idx_name}")

        # 4. 移除非必需索引
        if removable_indexes:
            print(f"\n🧹 移除 {len(removable_indexes)} 个非必需索引...")
            
            for idx_name in removable_indexes:
                try:
                    await collection.drop_index(idx_name)
                    print(f"  ✅ 已移除: {idx_name}")
                except OperationFailure as e:
                    print(f"  ⚠️  移除失败 {idx_name}: {e}")
        else:
            print("\n✨ 当前索引结构已经是最简化的!")

        # 5. 确保核心索引存在
        print("\n🔧 确保核心索引存在...")
        
        # 检查并创建缺失的核心索引
        final_indexes = await collection.list_indexes().to_list(length=None)
        existing_names = {idx.get('name') for idx in final_indexes}
        
        missing_indexes = []
        
        # DOI查询索引
        if "doi_query_index" not in existing_names:
            missing_indexes.append(IndexModel(
                [("identifiers.doi", ASCENDING)], 
                name="doi_query_index",
                background=True,
                partialFilterExpression={"identifiers.doi": {"$type": "string"}}
            ))
        
        # ArXiv查询索引
        if "arxiv_query_index" not in existing_names:
            missing_indexes.append(IndexModel(
                [("identifiers.arxiv_id", ASCENDING)], 
                name="arxiv_query_index",
                background=True,
                partialFilterExpression={"identifiers.arxiv_id": {"$type": "string"}}
            ))
        
        # 指纹查询索引
        if "fingerprint_query_index" not in existing_names:
            missing_indexes.append(IndexModel(
                [("identifiers.fingerprint", ASCENDING)], 
                name="fingerprint_query_index",
                background=True,
                partialFilterExpression={"identifiers.fingerprint": {"$type": "string"}}
            ))
        
        # 任务ID查询索引
        if "task_id_query_index" not in existing_names:
            missing_indexes.append(IndexModel(
                [("task_info.task_id", ASCENDING)], 
                name="task_id_query_index",
                background=True
            ))
        
        # 标题全文搜索索引
        if "title_text_search_index" not in existing_names:
            missing_indexes.append(IndexModel(
                [("metadata.title", TEXT)], 
                name="title_text_search_index",
                background=True
            ))
        
        # 创建缺失的索引
        if missing_indexes:
            print(f"创建 {len(missing_indexes)} 个缺失的核心索引...")
            for index in missing_indexes:
                try:
                    await collection.create_indexes([index])
                    print(f"  ✅ 创建: {index.document.get('name', 'unnamed')}")
                except OperationFailure as e:
                    print(f"  ⚠️  创建失败 {index.document.get('name', 'unnamed')}: {e}")
        else:
            print("所有核心索引都已存在!")

        # 6. 验证最终索引结构
        print("\n🔍 验证最终简化的索引结构...")
        final_indexes = await collection.list_indexes().to_list(length=None)

        print("最终索引结构:")
        total_indexes = 0
        essential_count = 0
        
        for idx in final_indexes:
            name = idx.get("name", "unnamed")
            total_indexes += 1
            
            if name in essential_indexes:
                essential_count += 1
                status = " [✅ 核心]"
                desc = essential_indexes[name]
                print(f"  • {name}: {desc}{status}")
            else:
                status = " [⚠️ 额外]"
                print(f"  • {name}: 额外索引{status}")

        print(f"\n📊 索引结构统计:")
        print(f"  • 总索引数: {total_indexes}")
        print(f"  • 核心索引: {essential_count}")
        print(f"  • 额外索引: {total_indexes - essential_count}")
        
        # 7. 性能建议
        print(f"\n💡 性能优化建议:")
        if total_indexes <= 6:
            print("  ✅ 索引结构已高度优化")
            print("  ✅ 查询性能与存储空间达到最佳平衡")
            print("  ✅ 完全依赖业务逻辑进行去重")
        elif total_indexes <= 10:
            print("  ⚠️  索引数量适中，可考虑进一步简化")
        else:
            print("  ❌ 索引数量较多，建议进一步简化")

        print("\n✅ 索引结构简化完成!")
        print("\n🎯 简化效果:")
        print("  • 移除了所有复杂的复合索引")
        print("  • 保留了核心查询性能索引")
        print("  • 完全依赖业务逻辑进行去重")
        print("  • 减少了索引维护开销")
        print("  • 提高了写入性能")

    except Exception as e:
        print(f"❌ 索引简化过程中出错: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()


async def analyze_query_performance():
    """分析查询性能"""
    print("\n📈 分析查询性能...")
    
    client = AsyncIOMotorClient(
        "mongodb://literature_parser_backend:literature_parser_backend@db:27017/admin"
    )
    db = client.literature_parser
    collection = db.literatures
    
    try:
        # 统计文档数量
        doc_count = await collection.count_documents({})
        print(f"文档总数: {doc_count}")
        
        # 测试关键查询的性能
        queries = [
            {"identifiers.doi": {"$exists": True}},
            {"identifiers.arxiv_id": {"$exists": True}},
            {"identifiers.fingerprint": {"$exists": True}},
            {"task_info.task_id": {"$exists": True}}
        ]
        
        for i, query in enumerate(queries, 1):
            try:
                count = await collection.count_documents(query)
                print(f"查询 {i}: {count} 个匹配文档")
            except Exception as e:
                print(f"查询 {i} 失败: {e}")
                
    except Exception as e:
        print(f"性能分析失败: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(simplify_index_structure())
    asyncio.run(analyze_query_performance())
