#!/usr/bin/env python3
"""
修复Literature节点的title属性问题
将metadata.title提取出来作为独立的title属性
"""

import asyncio
import json
import os
from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.neo4j import connect_to_mongodb
from literature_parser_backend.settings import Settings

# 设置正确的Neo4j URI
os.environ['LITERATURE_PARSER_BACKEND_NEO4J_URI'] = 'bolt://localhost:7687'

async def fix_literature_titles():
    """修复所有Literature节点的title属性"""
    
    # 初始化连接
    settings = Settings()
    await connect_to_mongodb(settings)
    
    # 初始化DAO
    relationship_dao = RelationshipDAO.create_from_global_connection()
    
    try:
        print("🔧 开始修复Literature节点的title属性")
        print("=" * 60)
        
        # 1. 查看当前状态
        print("📊 检查当前Literature节点状态...")
        
        check_query = """
        MATCH (n:Literature)
        RETURN n.lid as lid, 
               n.title as direct_title, 
               n.metadata as metadata
        ORDER BY n.lid
        """
        
        results = await relationship_dao._execute_cypher(check_query)
        
        print(f"找到 {len(results)} 个Literature节点")
        print("-" * 60)
        
        updated_count = 0
        skipped_count = 0
        
        for i, record in enumerate(results, 1):
            lid = record['lid']
            direct_title = record['direct_title']
            metadata = relationship_dao._parse_json_field(record['metadata'])
            
            print(f"{i}. 处理 LID: {lid}")
            
            # 检查是否已经有title属性
            if direct_title:
                print(f"   ✅ 已有title: {direct_title}")
                skipped_count += 1
                continue
            
            # 从metadata中提取title
            if metadata and 'title' in metadata and metadata['title']:
                title_from_metadata = metadata['title']
                print(f"   📝 从metadata提取title: {title_from_metadata}")
                
                # 更新节点，添加title属性
                update_query = """
                MATCH (n:Literature {lid: $lid})
                SET n.title = $title
                RETURN n.lid as lid, n.title as new_title
                """
                
                update_result = await relationship_dao._execute_cypher(
                    update_query, 
                    {"lid": lid, "title": title_from_metadata}
                )
                
                if update_result:
                    print(f"   ✅ 更新成功: {update_result[0]['new_title']}")
                    updated_count += 1
                else:
                    print(f"   ❌ 更新失败")
            else:
                print(f"   ⚠️ metadata中没有title信息")
                print(f"   📄 metadata: {metadata}")
                skipped_count += 1
            
            print()
        
        print("=" * 60)
        print("🎉 修复完成!")
        print(f"✅ 更新了 {updated_count} 个节点")
        print(f"⏭️ 跳过了 {skipped_count} 个节点")
        print()
        
        # 2. 验证修复结果
        print("🔍 验证修复结果...")
        verify_query = """
        MATCH (n:Literature)
        RETURN n.lid as lid, 
               n.title as title,
               CASE WHEN n.title IS NOT NULL THEN 'YES' ELSE 'NO' END as has_title
        ORDER BY n.lid
        """
        
        verify_results = await relationship_dao._execute_cypher(verify_query)
        
        print(f"📊 验证结果:")
        print("-" * 60)
        
        has_title_count = 0
        for result in verify_results:
            lid = result['lid']
            title = result['title'] or "无标题"
            has_title = result['has_title']
            
            if has_title == 'YES':
                has_title_count += 1
                status = "✅"
            else:
                status = "❌"
            
            print(f"{status} {lid}: {title[:50]}{'...' if len(str(title)) > 50 else ''}")
        
        print("-" * 60)
        print(f"📈 总结: {has_title_count}/{len(verify_results)} 个节点有title属性")
        
        # 3. 测试API响应是否正确
        print("\n🧪 测试API响应...")
        test_lids = ["2017-ashish-aayn-fa59", "2017-vaswani-aayn-9572"]
        
        for lid in test_lids:
            title_query = """
            MATCH (n:Literature {lid: $lid})
            RETURN n.lid as lid, n.title as title
            """
            
            test_result = await relationship_dao._execute_cypher(title_query, {"lid": lid})
            if test_result:
                print(f"📋 {lid}: {test_result[0]['title']}")
            else:
                print(f"❌ 未找到 {lid}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_literature_titles())




