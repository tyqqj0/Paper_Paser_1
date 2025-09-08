#!/usr/bin/env python3
"""
分析数据库中的重复论文问题
"""

import asyncio
import json
from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_neo4j
from literature_parser_backend.settings import Settings

# 已知的重复论文LID
KNOWN_DUPLICATES = [
    "2017-ashish-aayn-fa59",   # Attention is All you Need
    "2017-vaswani-aayn-9572",  # Attention Is All You Need
]

async def analyze_duplicate_papers():
    """详细分析重复论文的元数据"""
    
    # 初始化连接
    settings = Settings()
    await connect_to_neo4j(settings)
    
    # 初始化DAO
    relationship_dao = RelationshipDAO.create_from_global_connection()
    
    try:
        print("📊 分析重复论文详细信息")
        print("=" * 80)
        
        for i, lid in enumerate(KNOWN_DUPLICATES, 1):
            print(f"\n{i}. 分析 LID: {lid}")
            print("-" * 50)
            
            # 查询完整的节点信息
            query = """
            MATCH (n:Literature {lid: $lid})
            RETURN n.lid as lid, 
                   n.title as title,
                   n.metadata as metadata,
                   n.doi as doi,
                   n.type as type,
                   n.created_at as created_at,
                   n.updated_at as updated_at
            """
            
            result = await relationship_dao._execute_cypher(query, {"lid": lid})
            
            if result:
                record = result[0]
                print(f"📄 标题: {record['title']}")
                print(f"🆔 LID: {record['lid']}")
                print(f"📖 DOI: {record['doi']}")
                print(f"📂 类型: {record['type']}")
                print(f"📅 创建时间: {record['created_at']}")
                print(f"🔄 更新时间: {record['updated_at']}")
                
                # 解析元数据
                metadata = relationship_dao._parse_json_field(record['metadata'])
                if metadata:
                    print(f"👥 作者: {metadata.get('authors', 'N/A')}")
                    print(f"📆 年份: {metadata.get('year', 'N/A')}")
                    print(f"📰 期刊: {metadata.get('journal', 'N/A')}")
                    print(f"🏛️ 出版商: {metadata.get('publisher', 'N/A')}")
                    print(f"📝 摘要长度: {len(str(metadata.get('abstract', '')))}")
                    
                    # 显示完整的元数据结构
                    print(f"🔍 完整元数据:")
                    print(json.dumps(metadata, indent=2, ensure_ascii=False))
                else:
                    print("⚠️ 无法解析元数据")
            else:
                print(f"❌ 未找到 LID: {lid}")
        
        # 查找更多潜在的重复项
        print(f"\n\n🔎 寻找其他潜在重复项...")
        print("=" * 80)
        
        # 按标题相似性查找潜在重复
        similar_titles_query = """
        MATCH (n:Literature)
        WITH n.title as title, collect(n) as nodes
        WHERE size(nodes) > 1
        RETURN title, [node in nodes | node.lid] as lids, size(nodes) as count
        ORDER BY count DESC
        """
        
        similar_results = await relationship_dao._execute_cypher(similar_titles_query)
        
        if similar_results:
            print(f"📊 找到 {len(similar_results)} 组相同标题的论文:")
            for i, record in enumerate(similar_results, 1):
                print(f"{i}. 标题: {record['title']}")
                print(f"   LIDs: {record['lids']}")
                print(f"   数量: {record['count']}")
                print()
        else:
            print("✅ 未发现完全相同标题的重复论文")
            
        # 按DOI查找重复
        print(f"\n🔎 按DOI查找重复...")
        print("-" * 50)
        
        duplicate_doi_query = """
        MATCH (n:Literature)
        WHERE n.doi IS NOT NULL AND n.doi <> ""
        WITH n.doi as doi, collect(n) as nodes
        WHERE size(nodes) > 1
        RETURN doi, [node in nodes | node.lid] as lids, size(nodes) as count
        ORDER BY count DESC
        """
        
        doi_results = await relationship_dao._execute_cypher(duplicate_doi_query)
        
        if doi_results:
            print(f"📊 找到 {len(doi_results)} 组相同DOI的论文:")
            for i, record in enumerate(doi_results, 1):
                print(f"{i}. DOI: {record['doi']}")
                print(f"   LIDs: {record['lids']}")
                print(f"   数量: {record['count']}")
                print()
        else:
            print("✅ 未发现相同DOI的重复论文")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 使用正确的Neo4j URI
    import os
    os.environ['LITERATURE_PARSER_BACKEND_NEO4J_URI'] = 'bolt://localhost:7687'
    
    asyncio.run(analyze_duplicate_papers())




