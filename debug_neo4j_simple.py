#!/usr/bin/env python3
"""
简化版Neo4j Debug脚本 - 通过HTTP API查询
"""

import asyncio
import httpx
import json
import base64
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

class Neo4jDebugger:
    def __init__(self):
        self.base_url = "http://localhost:7474"
        # Neo4j用户名密码 (根据docker-compose.yml)
        credentials = base64.b64encode(b"neo4j:literature_parser_neo4j").decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json"
        }
    
    async def run_query(self, cypher_query):
        """执行Cypher查询"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/db/data/transaction/commit",
                    headers=self.headers,
                    json={
                        "statements": [
                            {"statement": cypher_query}
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("errors"):
                        console.print(f"❌ Neo4j查询错误: {data['errors']}")
                        return None
                    return data.get("results", [{}])[0].get("data", [])
                else:
                    console.print(f"❌ HTTP错误 {response.status_code}: {response.text}")
                    return None
                    
            except Exception as e:
                console.print(f"❌ 连接失败: {e}")
                return None
    
    async def debug_citation_system(self):
        """Debug引用关系系统"""
        
        console.print(Panel.fit("🔍 Neo4j引用关系系统Debug (简化版)", style="bold blue"))
        
        # 1. 节点统计
        console.print("\n📊 节点统计:")
        
        queries = {
            "Literature节点": "MATCH (n:Literature) RETURN count(n) as count",
            "Unresolved节点": "MATCH (n:Unresolved) RETURN count(n) as count", 
            "CITES关系": "MATCH ()-[r:CITES]->() RETURN count(r) as count"
        }
        
        stats = {}
        for name, query in queries.items():
            result = await self.run_query(query)
            if result:
                count = result[0]["row"][0] if result else 0
                stats[name] = count
                console.print(f"   📈 {name}: {count}")
            else:
                console.print(f"   ❌ {name}: 查询失败")
                stats[name] = 0
        
        # 2. Literature节点详情
        console.print("\n📚 Literature节点详情:")
        literature_query = """
        MATCH (lit:Literature)
        RETURN lit.lid as lid, 
               lit.metadata.title as title,
               lit.created_at as created_at
        ORDER BY lit.created_at DESC
        """
        result = await self.run_query(literature_query)
        if result:
            table = Table(title="Literature节点")
            table.add_column("LID", style="cyan")
            table.add_column("标题", style="green", max_width=50)
            table.add_column("创建时间", style="yellow")
            
            for row_data in result:
                row = row_data["row"]
                lid = row[0] or "N/A"
                title = row[1] or "No title"
                created_at = row[2] or "N/A"
                
                if len(title) > 47:
                    title = title[:47] + "..."
                if isinstance(created_at, str) and len(created_at) > 19:
                    created_at = created_at[:19]
                    
                table.add_row(lid, title, str(created_at))
            
            console.print(table)
        
        # 3. 引用关系详情
        console.print("\n🔗 引用关系详情:")
        citation_query = """
        MATCH (from_lit:Literature)-[r:CITES]->(to_node)
        RETURN from_lit.lid as from_lid,
               from_lit.metadata.title as from_title,
               labels(to_node) as to_labels,
               to_node.lid as to_lid,
               CASE 
                 WHEN 'Literature' IN labels(to_node) THEN to_node.metadata.title
                 WHEN 'Unresolved' IN labels(to_node) THEN coalesce(to_node.parsed_data.title, to_node.raw_text)
                 ELSE to_node.raw_text
               END as to_title,
               r.source as source
        ORDER BY from_lit.created_at DESC
        LIMIT 15
        """
        result = await self.run_query(citation_query)
        if result:
            citations_table = Table(title="引用关系 (最新15条)")
            citations_table.add_column("引用方", style="cyan", max_width=25)
            citations_table.add_column("被引用方", style="green", max_width=25)
            citations_table.add_column("类型", style="yellow")
            citations_table.add_column("来源", style="blue")
            
            for row_data in result:
                row = row_data["row"]
                from_title = (row[1] or "No title")[:22] + "..."
                to_labels = row[2] or []
                to_title = (row[4] or row[3] or "No title")[:22] + "..."
                to_type = "Literature" if "Literature" in to_labels else "Unresolved"
                source = row[5] or "N/A"
                
                citations_table.add_row(from_title, to_title, to_type, source)
            
            console.print(citations_table)
            console.print(f"📈 显示了前15条引用关系")
        
        # 4. Unresolved节点样例
        if stats.get("Unresolved节点", 0) > 0:
            console.print("\n❓ Unresolved节点样例:")
            unresolved_query = """
            MATCH (u:Unresolved)
            RETURN u.lid as lid,
                   u.raw_text as raw_text,
                   u.parsed_data.title as parsed_title
            ORDER BY u.created_at DESC
            LIMIT 8
            """
            result = await self.run_query(unresolved_query)
            if result:
                unresolved_table = Table(title="Unresolved节点样例 (最新8个)")
                unresolved_table.add_column("LID", style="cyan", max_width=20)
                unresolved_table.add_column("原始文本", style="green", max_width=35)
                unresolved_table.add_column("解析标题", style="yellow", max_width=25)
                
                for row_data in result:
                    row = row_data["row"]
                    lid = row[0] or "N/A"
                    raw_text = (row[1] or "")[:32] + "..." if len(row[1] or "") > 35 else (row[1] or "")
                    parsed_title = (row[2] or "")[:22] + "..." if len(row[2] or "") > 25 else (row[2] or "")
                    
                    unresolved_table.add_row(lid, raw_text, parsed_title)
                
                console.print(unresolved_table)
        
        # 5. 总结报告
        console.print("\n" + "="*60)
        console.print(Panel.fit("📊 Debug总结报告", style="bold green"))
        
        literature_count = stats.get("Literature节点", 0)
        unresolved_count = stats.get("Unresolved节点", 0) 
        cites_count = stats.get("CITES关系", 0)
        
        console.print(f"📚 Literature节点: {literature_count}")
        console.print(f"❓ Unresolved节点: {unresolved_count}")
        console.print(f"🔗 CITES关系: {cites_count}")
        
        if literature_count > 0 and unresolved_count > 0 and cites_count > 0:
            console.print("\n✅ 引用关系系统运行正常！")
            console.print("   - 文献节点已创建")
            console.print("   - 引用解析已执行") 
            console.print("   - Unresolved悬空节点已创建")
            console.print("   - CITES关系已建立")
            console.print(f"\n📊 系统状态: {literature_count}篇文献，{unresolved_count}个悬空引用，{cites_count}个引用关系")
        elif literature_count > 0 and cites_count == 0:
            console.print("\n⚠️ 引用关系系统部分工作：")
            console.print("   - 文献节点已创建 ✅")
            console.print("   - 引用解析未执行 ❌")
        else:
            console.print("\n❌ 引用关系系统未正常工作")

async def main():
    debugger = Neo4jDebugger()
    await debugger.debug_citation_system()

if __name__ == "__main__":
    asyncio.run(main())
