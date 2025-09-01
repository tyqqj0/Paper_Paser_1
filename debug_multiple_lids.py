#!/usr/bin/env python3
"""
调试多个LID查询问题
"""

import asyncio
from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_mongodb
from literature_parser_backend.settings import Settings

async def debug_multiple_lids():
    """调试多个LID查询问题"""
    
    # 初始化连接
    settings = Settings()
    await connect_to_mongodb(settings)
    
    # 初始化DAO
    relationship_dao = RelationshipDAO.create_from_global_connection()
    
    target_lids = ["2017-vaswani-aayn-6096", "2018-devlin-bptdbt-dbc3", "2020-dosovits-iwwtir-e64e"]
    print(f"🎯 测试LID: {target_lids}")
    
    try:
        # 1. 测试单个查询
        print("\n📊 第一步：逐个测试每个LID")
        for lid in target_lids:
            query = """
            MATCH (lit:Literature)
            WHERE lit.lid = $lid
            RETURN lit.lid as lid, lit.metadata as metadata
            """
            result = await relationship_dao._execute_cypher(query, {"lid": lid})
            print(f"   {lid}: {len(result)} 个节点")
            if result:
                metadata = relationship_dao._parse_json_field(result[0]['metadata'])
                print(f"      Title: {metadata.get('title', 'N/A')}")
        
        # 2. 测试批量查询
        print(f"\n📊 第二步：批量查询所有LID")
        query = """
        MATCH (lit:Literature)
        WHERE lit.lid IN $target_lids
        RETURN lit.lid as lid, lit.metadata as metadata
        """
        result = await relationship_dao._execute_cypher(query, {"target_lids": target_lids})
        print(f"   批量查询: {len(result)} 个节点")
        for record in result:
            metadata = relationship_dao._parse_json_field(record['metadata'])
            print(f"     - {record['lid']}: {metadata.get('title', 'N/A')}")
        
        # 3. 测试RelationshipDAO的get_internal_citation_graph方法
        print(f"\n🧪 第三步：测试get_internal_citation_graph方法")
        graph_result = await relationship_dao.get_internal_citation_graph(target_lids)
        print(f"   方法返回结果:")
        print(f"     - 节点数: {len(graph_result.get('nodes', []))}")
        print(f"     - 边数: {len(graph_result.get('edges', []))}")
        print(f"     - Target LIDs: {graph_result.get('target_lids', [])}")
        
        if graph_result.get('nodes'):
            print("   节点详情:")
            for node in graph_result['nodes']:
                print(f"     - {node['lid']}: {node['title']}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_multiple_lids())
