#!/usr/bin/env python3
"""
列出所有可用的LID
"""

import asyncio
from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_mongodb
from literature_parser_backend.settings import Settings

async def list_all_lids():
    """列出所有可用的Literature LID"""
    
    # 初始化连接
    settings = Settings()
    await connect_to_mongodb(settings)
    
    # 初始化DAO
    relationship_dao = RelationshipDAO.create_from_global_connection()
    
    try:
        # 查询所有Literature节点的LID
        query = """
        MATCH (n:Literature) 
        RETURN n.lid as lid, n.metadata as metadata
        ORDER BY n.lid
        """
        
        result = await relationship_dao._execute_cypher(query)
        print(f"📊 找到 {len(result)} 个Literature节点:")
        print("=" * 80)
        
        for i, record in enumerate(result, 1):
            lid = record['lid']
            metadata = relationship_dao._parse_json_field(record['metadata'])
            title = metadata.get('title', 'N/A')
            
            print(f"{i:2d}. LID: {lid}")
            print(f"    Title: {title}")
            print()
            
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    asyncio.run(list_all_lids())
