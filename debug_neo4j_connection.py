#!/usr/bin/env python3
"""
调试Neo4j连接问题
"""

import asyncio
from neo4j import AsyncGraphDatabase

async def test_neo4j_connection():
    """测试Neo4j连接"""
    
    # 测试不同的连接URI
    test_uris = [
        "bolt://localhost:7687",
        "bolt://127.0.0.1:7687", 
        "neo4j://localhost:7687",
        "neo4j://127.0.0.1:7687"
    ]
    
    credentials = ("neo4j", "literature_parser_neo4j")
    
    for uri in test_uris:
        print(f"🔗 测试连接: {uri}")
        try:
            driver = AsyncGraphDatabase.driver(uri, auth=credentials)
            
            # 测试连接
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                print(f"✅ 连接成功！返回值: {record['test']}")
                
            await driver.close()
            print("🎉 此URI可用！")
            break
            
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print()

if __name__ == "__main__":
    asyncio.run(test_neo4j_connection())


