#!/usr/bin/env python3
"""
检查Neo4j数据库中的文献和关系数据
"""

import asyncio
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_neo4j, disconnect_from_neo4j
from literature_parser_backend.settings import get_settings

async def check_neo4j_data():
    """检查Neo4j中的数据"""
    print("🔍 检查Neo4j数据库内容")
    print("=" * 50)
    
    try:
        # 初始化数据库连接
        print("🔌 初始化数据库连接...")
        settings = get_settings()
        await connect_to_neo4j(settings)
        print("   ✅ 数据库连接成功")
        
        # 检查文献数据
        print("📚 1. 检查文献数据...")
        literature_dao = LiteratureDAO.create_from_global_connection()
        
        # 查询所有文献的数量和一些示例
        async with literature_dao._get_session() as session:
            # 统计文献数量
            result = await session.run("MATCH (n:Literature) RETURN count(n) as total")
            record = await result.single()
            total_literature = record["total"] if record else 0
            print(f"   总文献数: {total_literature}")
            
            if total_literature > 0:
                # 获取一些示例
                result = await session.run("""
                    MATCH (n:Literature) 
                    RETURN n.lid as lid, n.metadata.title as title
                    LIMIT 5
                """)
                
                print("   最近的文献:")
                async for record in result:
                    lid = record["lid"]
                    title = record["title"] or "No title"
                    print(f"     - {lid}: {title[:50]}...")
            
            print()
            
            # 检查关系数据
            print("🔗 2. 检查引用关系...")
            result = await session.run("MATCH ()-[r:CITES]->() RETURN count(r) as total")
            record = await result.single()
            total_relations = record["total"] if record else 0
            print(f"   总关系数: {total_relations}")
            
            if total_relations > 0:
                # 获取一些关系示例
                result = await session.run("""
                    MATCH (from:Literature)-[r:CITES]->(to:Literature)
                    RETURN from.lid as from_lid, to.lid as to_lid, 
                           r.confidence as confidence, r.source as source
                    LIMIT 5
                """)
                
                print("   关系示例:")
                async for record in result:
                    from_lid = record["from_lid"]
                    to_lid = record["to_lid"] 
                    confidence = record["confidence"]
                    source = record["source"]
                    print(f"     - {from_lid} → {to_lid} (置信度: {confidence}, 来源: {source})")
            
            print()
            
            # 如果有数据，测试关系图API
            if total_literature > 0:
                print("🕸️ 3. 测试真实数据的关系图...")
                
                # 获取一些LID
                result = await session.run("MATCH (n:Literature) RETURN n.lid as lid LIMIT 3")
                lids = []
                async for record in result:
                    lids.append(record["lid"])
                
                if lids:
                    print(f"   使用LID: {', '.join(lids)}")
                    
                    # 测试关系图API
                    relationship_dao = RelationshipDAO.create_from_global_connection()
                    graph_data = await relationship_dao.get_citation_graph(
                        center_lids=lids,
                        max_depth=2,
                        min_confidence=0.1  # 低阈值以获取更多结果
                    )
                    
                    print(f"   关系图结果:")
                    print(f"     节点数: {len(graph_data.get('nodes', []))}")
                    print(f"     边数: {len(graph_data.get('edges', []))}")
                    
                    # 显示一些详细信息
                    nodes = graph_data.get('nodes', [])
                    edges = graph_data.get('edges', [])
                    
                    if nodes:
                        print(f"   节点示例:")
                        for node in nodes[:3]:
                            print(f"     - {node.get('lid')}: {node.get('title', 'No title')[:30]}...")
                    
                    if edges:
                        print(f"   边示例:")
                        for edge in edges[:3]:
                            print(f"     - {edge.get('from_lid')} → {edge.get('to_lid')} (置信度: {edge.get('confidence')})")
                    else:
                        print(f"   ⚠️ 没有找到引用关系")
            else:
                print("⚠️ 数据库中没有文献数据")
                print("💡 建议: 先运行一些论文解析任务来生成数据")
                
    except Exception as e:
        print(f"❌ 检查数据时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理数据库连接
        print("🔌 关闭数据库连接...")
        await disconnect_from_mongodb()

if __name__ == "__main__":
    asyncio.run(check_neo4j_data())
