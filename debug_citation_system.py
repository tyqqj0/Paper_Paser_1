#!/usr/bin/env python3
"""
引用关系系统Debug脚本

直接查询Neo4j数据库，验证：
1. Literature节点数量
2. Unresolved节点数量  
3. CITES关系数量
4. 具体的引用关系数据
"""

import asyncio
import sys
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 添加项目路径
sys.path.append('.')

console = Console()

async def debug_neo4j_direct():
    """直接查询Neo4j数据库进行debug"""
    
    try:
        # 使用系统的Neo4j连接
        from literature_parser_backend.db.connection import get_neo4j_driver
        
        driver = get_neo4j_driver()
        
        console.print(Panel.fit("🔍 Neo4j引用关系系统Debug", style="bold blue"))
        
        # 1. 查询所有节点统计
        console.print("\n📊 节点统计:")
        async with driver.session() as session:
            
            # Literature节点数量
            result = await session.run("MATCH (n:Literature) RETURN count(n) as count")
            literature_count = (await result.single())["count"]
            console.print(f"   📚 Literature节点: {literature_count}")
            
            # Unresolved节点数量
            result = await session.run("MATCH (n:Unresolved) RETURN count(n) as count")
            unresolved_count = (await result.single())["count"]
            console.print(f"   ❓ Unresolved节点: {unresolved_count}")
            
            # CITES关系数量
            result = await session.run("MATCH ()-[r:CITES]->() RETURN count(r) as count")
            cites_count = (await result.single())["count"]
            console.print(f"   🔗 CITES关系: {cites_count}")
            
        # 2. 查询所有Literature节点详情
        console.print("\n📚 Literature节点详情:")
        async with driver.session() as session:
            query = """
            MATCH (lit:Literature)
            RETURN lit.lid as lid, 
                   lit.metadata.title as title,
                   lit.created_at as created_at
            ORDER BY lit.created_at DESC
            """
            result = await session.run(query)
            
            table = Table(title="Literature节点")
            table.add_column("LID", style="cyan")
            table.add_column("标题", style="green", max_width=50)
            table.add_column("创建时间", style="yellow")
            
            async for record in result:
                title = record["title"] or "No title"
                if len(title) > 47:
                    title = title[:47] + "..."
                table.add_row(
                    record["lid"],
                    title,
                    record["created_at"][:19] if record["created_at"] else "N/A"
                )
            
            console.print(table)
        
        # 3. 查询文献的引用关系 
        console.print("\n🔗 文献引用关系详情:")
        async with driver.session() as session:
            query = """
            MATCH (from_lit:Literature)-[r:CITES]->(to_node)
            RETURN from_lit.lid as from_lid,
                   from_lit.metadata.title as from_title,
                   labels(to_node) as to_labels,
                   to_node.lid as to_lid,
                   CASE 
                     WHEN 'Literature' IN labels(to_node) THEN to_node.metadata.title
                     WHEN 'Unresolved' IN labels(to_node) THEN to_node.parsed_data.title
                     ELSE to_node.raw_text
                   END as to_title,
                   r.source as source,
                   r.confidence as confidence
            ORDER BY from_lit.created_at DESC
            LIMIT 20
            """
            result = await session.run(query)
            
            citations_table = Table(title="引用关系 (最新20条)")
            citations_table.add_column("引用方", style="cyan", max_width=25)
            citations_table.add_column("被引用方", style="green", max_width=25) 
            citations_table.add_column("类型", style="yellow")
            citations_table.add_column("置信度", style="magenta")
            citations_table.add_column("来源", style="blue")
            
            count = 0
            async for record in result:
                count += 1
                from_title = (record["from_title"] or "No title")[:22] + "..."
                to_title = (record["to_title"] or record["to_lid"] or "No title")[:22] + "..."
                to_type = "Literature" if "Literature" in record["to_labels"] else "Unresolved"
                confidence = f"{record['confidence']:.2f}" if record["confidence"] else "N/A"
                source = record["source"] or "N/A"
                
                citations_table.add_row(
                    from_title,
                    to_title,
                    to_type,
                    confidence,
                    source
                )
            
            console.print(citations_table)
            console.print(f"📈 显示了前20条引用关系，共查询到 {count} 条")
        
        # 4. 查询Unresolved节点样例
        if unresolved_count > 0:
            console.print("\n❓ Unresolved节点样例:")
            async with driver.session() as session:
                query = """
                MATCH (u:Unresolved)
                RETURN u.lid as lid,
                       u.raw_text as raw_text,
                       u.parsed_data.title as parsed_title,
                       u.created_at as created_at
                ORDER BY u.created_at DESC
                LIMIT 10
                """
                result = await session.run(query)
                
                unresolved_table = Table(title="Unresolved节点样例 (最新10个)")
                unresolved_table.add_column("LID", style="cyan", max_width=20)
                unresolved_table.add_column("原始文本", style="green", max_width=40)
                unresolved_table.add_column("解析标题", style="yellow", max_width=30)
                
                async for record in result:
                    raw_text = (record["raw_text"] or "")[:37] + "..." if len(record["raw_text"] or "") > 40 else (record["raw_text"] or "")
                    parsed_title = (record["parsed_title"] or "")[:27] + "..." if len(record["parsed_title"] or "") > 30 else (record["parsed_title"] or "")
                    
                    unresolved_table.add_row(
                        record["lid"],
                        raw_text,
                        parsed_title
                    )
                
                console.print(unresolved_table)
        
        # 5. 每个文献的引用统计
        console.print("\n📊 每个文献的引用统计:")
        async with driver.session() as session:
            query = """
            MATCH (lit:Literature)
            OPTIONAL MATCH (lit)-[:CITES]->(out_target)
            OPTIONAL MATCH (in_source)-[:CITES]->(lit)
            RETURN lit.lid as lid,
                   lit.metadata.title as title,
                   count(DISTINCT out_target) as outgoing_citations,
                   count(DISTINCT in_source) as incoming_citations
            ORDER BY (count(DISTINCT out_target) + count(DISTINCT in_source)) DESC
            """
            result = await session.run(query)
            
            stats_table = Table(title="文献引用统计")
            stats_table.add_column("LID", style="cyan")
            stats_table.add_column("标题", style="green", max_width=30)
            stats_table.add_column("出度", style="yellow")
            stats_table.add_column("入度", style="magenta")
            stats_table.add_column("总度", style="blue")
            
            async for record in result:
                title = (record["title"] or "No title")[:27] + "..." if len(record["title"] or "") > 30 else (record["title"] or "No title")
                outgoing = record["outgoing_citations"] or 0
                incoming = record["incoming_citations"] or 0
                total = outgoing + incoming
                
                stats_table.add_row(
                    record["lid"],
                    title,
                    str(outgoing),
                    str(incoming),
                    str(total)
                )
            
            console.print(stats_table)
        
        # 6. 总结报告
        console.print("\n" + "="*60)
        console.print(Panel.fit("📊 Debug总结报告", style="bold green"))
        
        console.print(f"📚 Literature节点: {literature_count}")
        console.print(f"❓ Unresolved节点: {unresolved_count}")
        console.print(f"🔗 CITES关系: {cites_count}")
        
        if literature_count > 0 and unresolved_count > 0 and cites_count > 0:
            console.print("\n✅ 引用关系系统运行正常！")
            console.print("   - 文献节点已创建")
            console.print("   - 引用解析已执行")
            console.print("   - Unresolved悬空节点已创建")
            console.print("   - CITES关系已建立")
        elif literature_count > 0 and cites_count == 0:
            console.print("\n⚠️ 引用关系系统部分工作：")
            console.print("   - 文献节点已创建 ✅")
            console.print("   - 引用解析未执行 ❌")
        else:
            console.print("\n❌ 引用关系系统未正常工作")
            
        await driver.close()
        
    except Exception as e:
        console.print(f"❌ Debug失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    await debug_neo4j_direct()

if __name__ == "__main__":
    asyncio.run(main())
