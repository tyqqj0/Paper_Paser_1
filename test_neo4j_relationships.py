#!/usr/bin/env python3
"""
Neo4j引用关系直接查询工具

用于验证Neo4j中的引用关系数据完整性
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 导入项目的Neo4j连接和DAO
import sys
sys.path.append('.')

from literature_parser_backend.db.relationship_dao import RelationshipDAO
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.connection import get_neo4j_connection

console = Console()
logger = logging.getLogger(__name__)

class Neo4jRelationshipInspector:
    """Neo4j引用关系检查器"""
    
    def __init__(self):
        self.relationship_dao = None
        self.literature_dao = None
        
    async def initialize(self):
        """初始化数据库连接"""
        try:
            # 初始化Neo4j连接
            self.relationship_dao = RelationshipDAO.create_from_global_connection()
            self.literature_dao = LiteratureDAO.create_from_global_connection()
            console.print("✅ Neo4j连接初始化成功")
        except Exception as e:
            console.print(f"❌ 初始化失败: {e}")
            raise

    async def get_all_literature_nodes(self) -> List[Dict[str, Any]]:
        """获取所有文献节点"""
        try:
            async with self.relationship_dao._get_session() as session:
                query = """
                MATCH (lit:Literature)
                RETURN lit.lid as lid, 
                       lit.metadata.title as title,
                       lit.metadata.year as year,
                       lit.metadata.authors as authors
                ORDER BY lit.metadata.year DESC
                """
                
                result = await session.run(query)
                nodes = []
                async for record in result:
                    nodes.append({
                        "lid": record["lid"],
                        "title": record["title"] or "No title",
                        "year": record["year"],
                        "authors": record["authors"] or []
                    })
                
                return nodes
                
        except Exception as e:
            console.print(f"❌ 查询文献节点失败: {e}")
            return []

    async def get_all_relationships(self) -> List[Dict[str, Any]]:
        """获取所有引用关系"""
        try:
            async with self.relationship_dao._get_session() as session:
                query = """
                MATCH (from_lit:Literature)-[rel:CITES]->(to_lit:Literature)
                RETURN from_lit.lid as from_lid,
                       to_lit.lid as to_lid,
                       from_lit.metadata.title as from_title,
                       to_lit.metadata.title as to_title,
                       rel.confidence as confidence,
                       rel.source as source,
                       rel.created_at as created_at
                ORDER BY rel.confidence DESC
                """
                
                result = await session.run(query)
                relationships = []
                async for record in result:
                    relationships.append({
                        "from_lid": record["from_lid"],
                        "to_lid": record["to_lid"],
                        "from_title": record["from_title"] or "No title",
                        "to_title": record["to_title"] or "No title",
                        "confidence": record["confidence"],
                        "source": record["source"],
                        "created_at": record["created_at"]
                    })
                
                return relationships
                
        except Exception as e:
            console.print(f"❌ 查询引用关系失败: {e}")
            return []

    async def get_relationships_for_lid(self, lid: str) -> Dict[str, Any]:
        """获取特定LID的引用关系"""
        try:
            async with self.relationship_dao._get_session() as session:
                # 获取出度关系 (这个文献引用了谁)
                outgoing_query = """
                MATCH (from_lit:Literature {lid: $lid})-[rel:CITES]->(to_lit:Literature)
                RETURN to_lit.lid as to_lid,
                       to_lit.metadata.title as to_title,
                       rel.confidence as confidence,
                       rel.source as source
                ORDER BY rel.confidence DESC
                """
                
                # 获取入度关系 (谁引用了这个文献)
                incoming_query = """
                MATCH (from_lit:Literature)-[rel:CITES]->(to_lit:Literature {lid: $lid})
                RETURN from_lit.lid as from_lid,
                       from_lit.metadata.title as from_title,
                       rel.confidence as confidence,
                       rel.source as source
                ORDER BY rel.confidence DESC
                """
                
                # 执行查询
                outgoing_result = await session.run(outgoing_query, lid=lid)
                outgoing = []
                async for record in outgoing_result:
                    outgoing.append({
                        "lid": record["to_lid"],
                        "title": record["to_title"] or "No title",
                        "confidence": record["confidence"],
                        "source": record["source"]
                    })
                
                incoming_result = await session.run(incoming_query, lid=lid)
                incoming = []
                async for record in incoming_result:
                    incoming.append({
                        "lid": record["from_lid"],
                        "title": record["from_title"] or "No title",
                        "confidence": record["confidence"],
                        "source": record["source"]
                    })
                
                return {
                    "lid": lid,
                    "outgoing_citations": outgoing,
                    "incoming_citations": incoming,
                    "out_degree": len(outgoing),
                    "in_degree": len(incoming)
                }
                
        except Exception as e:
            console.print(f"❌ 查询LID {lid} 的关系失败: {e}")
            return {"lid": lid, "outgoing_citations": [], "incoming_citations": [], "out_degree": 0, "in_degree": 0}

    async def get_citation_graph(self, center_lids: List[str], max_depth: int = 2) -> Dict[str, Any]:
        """获取引用图（使用RelationshipDAO）"""
        try:
            graph_data = await self.relationship_dao.get_citation_graph(
                center_lids=center_lids,
                max_depth=max_depth,
                min_confidence=0.1  # 低阈值以获取更多数据
            )
            return graph_data
        except Exception as e:
            console.print(f"❌ 获取引用图失败: {e}")
            return {"nodes": [], "edges": []}

    async def display_literature_summary(self):
        """显示文献摘要"""
        console.print(Panel.fit("📚 文献库摘要", style="bold blue"))
        
        nodes = await self.get_all_literature_nodes()
        relationships = await self.get_all_relationships()
        
        console.print(f"📊 统计信息:")
        console.print(f"   文献总数: {len(nodes)}")
        console.print(f"   引用关系总数: {len(relationships)}")
        
        if nodes:
            # 显示文献列表
            table = Table(title="文献列表")
            table.add_column("LID", style="cyan")
            table.add_column("标题", style="green", max_width=50)
            table.add_column("年份", style="yellow")
            table.add_column("作者数", style="magenta")
            
            for node in nodes[:10]:  # 最多显示10条
                author_count = len(node["authors"]) if node["authors"] else 0
                table.add_row(
                    node["lid"],
                    node["title"][:47] + "..." if len(node["title"]) > 50 else node["title"],
                    str(node["year"]) if node["year"] else "N/A",
                    str(author_count)
                )
            
            console.print(table)
            
            if len(nodes) > 10:
                console.print(f"... 还有 {len(nodes) - 10} 篇文献")

    async def display_relationships_summary(self):
        """显示引用关系摘要"""
        console.print(Panel.fit("🔗 引用关系摘要", style="bold green"))
        
        relationships = await self.get_all_relationships()
        
        if relationships:
            # 显示引用关系列表
            table = Table(title="引用关系")
            table.add_column("引用方", style="cyan", max_width=30)
            table.add_column("被引用方", style="green", max_width=30)
            table.add_column("置信度", style="yellow")
            table.add_column("来源", style="magenta")
            
            for rel in relationships[:15]:  # 最多显示15条
                table.add_row(
                    rel["from_title"][:27] + "..." if len(rel["from_title"]) > 30 else rel["from_title"],
                    rel["to_title"][:27] + "..." if len(rel["to_title"]) > 30 else rel["to_title"],
                    f"{rel['confidence']:.2f}" if rel['confidence'] else "N/A",
                    rel["source"] or "Unknown"
                )
            
            console.print(table)
            
            if len(relationships) > 15:
                console.print(f"... 还有 {len(relationships) - 15} 个引用关系")
        else:
            console.print("⚠️ 未发现任何引用关系")

    async def test_citation_graph_api(self, lids: List[str]):
        """测试引用图API"""
        console.print(Panel.fit("🌐 测试引用图功能", style="bold magenta"))
        
        if not lids:
            console.print("⚠️ 没有LID可以测试")
            return
            
        console.print(f"🔍 测试LID: {lids}")
        
        graph_data = await self.get_citation_graph(lids, max_depth=2)
        
        console.print(f"📊 图数据结果:")
        console.print(f"   节点数: {len(graph_data.get('nodes', []))}")
        console.print(f"   边数: {len(graph_data.get('edges', []))}")
        
        if graph_data.get("nodes"):
            console.print("\n📋 节点详情:")
            for node in graph_data["nodes"][:5]:  # 最多显示5个节点
                console.print(f"   {node.get('lid', 'N/A')}: {node.get('title', 'No title')[:50]}")
                
        if graph_data.get("edges"):
            console.print("\n🔗 边详情:")
            for edge in graph_data["edges"][:5]:  # 最多显示5条边
                console.print(f"   {edge.get('from_lid', 'N/A')} -> {edge.get('to_lid', 'N/A')} (置信度: {edge.get('confidence', 'N/A')})")

async def main():
    """主函数"""
    inspector = Neo4jRelationshipInspector()
    
    try:
        await inspector.initialize()
        
        # 显示总体摘要
        await inspector.display_literature_summary()
        console.print("")
        await inspector.display_relationships_summary()
        
        # 获取一些LID进行测试
        nodes = await inspector.get_all_literature_nodes()
        if nodes:
            test_lids = [node["lid"] for node in nodes[:3]]  # 取前3个LID
            console.print("")
            await inspector.test_citation_graph_api(test_lids)
            
            # 显示每个LID的详细关系
            console.print(Panel.fit("🔍 详细关系分析", style="bold cyan"))
            for lid in test_lids:
                rel_data = await inspector.get_relationships_for_lid(lid)
                console.print(f"\n📄 LID: {lid}")
                console.print(f"   出度: {rel_data['out_degree']} (引用了 {rel_data['out_degree']} 篇文献)")
                console.print(f"   入度: {rel_data['in_degree']} (被 {rel_data['in_degree']} 篇文献引用)")
                
                if rel_data["outgoing_citations"]:
                    console.print("   引用的文献:")
                    for citation in rel_data["outgoing_citations"][:3]:
                        console.print(f"     -> {citation['title'][:40]}... (置信度: {citation['confidence']:.2f})")
                        
                if rel_data["incoming_citations"]:
                    console.print("   被引用:")
                    for citation in rel_data["incoming_citations"][:3]:
                        console.print(f"     <- {citation['title'][:40]}... (置信度: {citation['confidence']:.2f})")
        else:
            console.print("⚠️ 没有找到任何文献节点进行测试")
            
    except Exception as e:
        console.print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
