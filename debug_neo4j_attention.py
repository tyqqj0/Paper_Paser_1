#!/usr/bin/env python3
"""
Neo4j数据库调试脚本 - 专门查询attention论文
"""

import asyncio
import logging
from typing import List, Dict, Any

from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_mongodb
from literature_parser_backend.settings import Settings

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_neo4j_attention():
    """调试Neo4j中的attention论文数据"""
    
    print("🔍 Neo4j数据库调试 - Attention论文")
    print("=" * 60)
    
    # 初始化连接
    settings = Settings()
    await connect_to_mongodb(settings)
    
    # 初始化DAO
    relationship_dao = RelationshipDAO.create_from_global_connection()
    
    # 测试的LID
    target_lid = "2017-vaswani-aayn-6096"
    print(f"🎯 目标LID: {target_lid}")
    
    try:
        # 1. 查询所有Literature节点
        print("\n📊 第一步：查询所有Literature节点数量")
        query1 = "MATCH (n:Literature) RETURN count(n) as total"
        result1 = await relationship_dao._execute_cypher(query1)
        total_lit = result1[0]['total'] if result1 else 0
        print(f"   总Literature节点数: {total_lit}")
        
        # 2. 查询包含vaswani的节点
        print("\n🔍 第二步：查询包含'vaswani'的Literature节点")
        query2 = """
        MATCH (n:Literature) 
        WHERE n.lid CONTAINS 'vaswani' 
        RETURN n.lid, n.title 
        LIMIT 10
        """
        result2 = await relationship_dao._execute_cypher(query2)
        print(f"   找到 {len(result2)} 个包含'vaswani'的节点:")
        for record in result2:
            print(f"     - LID: {record['n.lid']}")
            print(f"       Title: {record.get('n.title', 'N/A')}")
        
        # 3. 精确查询目标LID
        print(f"\n🎯 第三步：精确查询LID '{target_lid}'")
        query3 = """
        MATCH (n:Literature) 
        WHERE n.lid = $lid
        RETURN n.lid, n.title, labels(n), keys(n)
        """
        result3 = await relationship_dao._execute_cypher(query3, {"lid": target_lid})
        print(f"   精确匹配结果: {len(result3)} 个节点")
        for record in result3:
            print(f"     - LID: {record['n.lid']}")
            print(f"     - Title: {record.get('n.title', 'N/A')}")
            print(f"     - Labels: {record['labels(n)']}")
            print(f"     - Properties: {record['keys(n)']}")
        
        # 4. 查询所有LID模式
        print("\n📋 第四步：查看所有Literature的LID模式")
        query4 = """
        MATCH (n:Literature) 
        RETURN n.lid 
        ORDER BY n.lid 
        LIMIT 10
        """
        result4 = await relationship_dao._execute_cypher(query4)
        print("   前10个LID样例:")
        for record in result4:
            print(f"     - {record['n.lid']}")
        
        # 5. 测试get_internal_citation_graph方法
        print(f"\n🧪 第五步：测试get_internal_citation_graph方法")
        graph_result = await relationship_dao.get_internal_citation_graph([target_lid])
        print(f"   方法返回结果:")
        print(f"     - 节点数: {len(graph_result.get('nodes', []))}")
        print(f"     - 边数: {len(graph_result.get('edges', []))}")
        print(f"     - Target LIDs: {graph_result.get('target_lids', [])}")
        
        if graph_result.get('nodes'):
            print("   节点详情:")
            for node in graph_result['nodes'][:3]:  # 只显示前3个
                print(f"     - {node}")
        
        # 6. 查看RelationshipDAO的实际查询
        print(f"\n🔧 第六步：查看RelationshipDAO的内部查询逻辑")
        # 模拟get_internal_citation_graph的查询
        internal_query = """
        MATCH (source:Literature)-[r:CITES]->(target:Literature)
        WHERE source.lid IN $target_lids AND target.lid IN $target_lids
        RETURN DISTINCT source, target, r
        """
        result6 = await relationship_dao._execute_cypher(internal_query, {"target_lids": [target_lid]})
        print(f"   内部关系查询结果: {len(result6)} 条关系")
        
        # 7. 查询任何包含这个LID的关系
        print(f"\n🔗 第七步：查询任何涉及该LID的关系")
        relation_query = """
        MATCH (n:Literature)-[r]-(m)
        WHERE n.lid = $lid
        RETURN type(r), labels(m), count(*) as cnt
        """
        result7 = await relationship_dao._execute_cypher(relation_query, {"lid": target_lid})
        print(f"   关系统计:")
        for record in result7:
            print(f"     - {record['type(r)']} -> {record['labels(m)']}: {record['cnt']} 次")
    
    except Exception as e:
        logger.error(f"❌ 调试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("🏁 调试完成")

if __name__ == "__main__":
    asyncio.run(debug_neo4j_attention())
