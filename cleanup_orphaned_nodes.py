#!/usr/bin/env python3
"""
Neo4j 数据库孤岛节点清理脚本

用于清理删除Literature节点后产生的孤岛Alias和Unresolved节点，
确保数据一致性，避免误删有效数据。

使用方法:
    python3 cleanup_orphaned_nodes.py [--dry-run] [--verbose]

参数:
    --dry-run: 只分析不删除，显示将要删除的节点
    --verbose: 显示详细信息
"""

import argparse
import asyncio
import logging
from typing import Dict, List

from neo4j import AsyncDriver, AsyncGraphDatabase

# Neo4j 连接配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "literature_parser_neo4j"

logger = logging.getLogger(__name__)


class OrphanedNodeCleaner:
    """孤岛节点清理器"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        """关闭数据库连接"""
        await self.driver.close()
    
    async def analyze_orphaned_nodes(self) -> Dict[str, List]:
        """
        分析孤岛节点，返回分析结果
        
        Returns:
            {
                "orphaned_aliases": [{"alias_value": "...", "alias_type": "..."}],
                "orphaned_unresolved": [{"lid": "...", "title": "..."}],
                "safe_unresolved": [{"lid": "...", "title": "...", "citing_count": N}]
            }
        """
        async with self.driver.session() as session:
            results = {
                "orphaned_aliases": [],
                "orphaned_unresolved": [],
                "safe_unresolved": []
            }
            
            # 1. 查找真正的孤岛Alias节点（没有任何关系的）
            orphaned_alias_query = """
            MATCH (alias:Alias)
            WHERE NOT EXISTS((alias)-[:ALIAS_OF]->(:Literature))
            AND NOT EXISTS((alias)-[]->())  // 没有任何出关系
            AND NOT EXISTS(()-[]->(alias))  // 没有任何入关系
            RETURN alias.alias_value as alias_value, 
                   alias.alias_type as alias_type
            ORDER BY alias.alias_value
            """
            
            result = await session.run(orphaned_alias_query)
            async for record in result:
                results["orphaned_aliases"].append({
                    "alias_value": record["alias_value"],
                    "alias_type": record["alias_type"]
                })
            
            # 2. 查找孤岛Unresolved节点（没有被任何Literature引用的）
            orphaned_unresolved_query = """
            MATCH (unresolved:Unresolved)
            WHERE NOT EXISTS((:Literature)-[:CITES]->(unresolved))
            RETURN unresolved.lid as lid, 
                   unresolved.parsed_title as title
            ORDER BY unresolved.lid
            """
            
            result = await session.run(orphaned_unresolved_query)
            async for record in result:
                results["orphaned_unresolved"].append({
                    "lid": record["lid"],
                    "title": record["title"] or "No title"
                })
            
            # 3. 查找被多个Literature引用的Unresolved节点（安全的，不应删除）
            safe_unresolved_query = """
            MATCH (unresolved:Unresolved)<-[:CITES]-(lit:Literature)
            WITH unresolved, count(lit) as citing_count
            WHERE citing_count > 1
            RETURN unresolved.lid as lid,
                   unresolved.parsed_title as title,
                   citing_count
            ORDER BY citing_count DESC, unresolved.lid
            """
            
            result = await session.run(safe_unresolved_query)
            async for record in result:
                results["safe_unresolved"].append({
                    "lid": record["lid"],
                    "title": record["title"] or "No title",
                    "citing_count": record["citing_count"]
                })
            
            return results
    
    async def clean_orphaned_nodes(self, dry_run: bool = True) -> Dict[str, int]:
        """
        清理孤岛节点
        
        Args:
            dry_run: 如果为True，只分析不删除
            
        Returns:
            清理统计信息
        """
        stats = {
            "orphaned_aliases_deleted": 0,
            "orphaned_unresolved_deleted": 0
        }
        
        if dry_run:
            print("🔍 DRY RUN MODE - 仅分析，不执行删除")
            analysis = await self.analyze_orphaned_nodes()
            
            print(f"\n📊 分析结果:")
            print(f"  - 孤岛Alias节点: {len(analysis['orphaned_aliases'])}")
            print(f"  - 孤岛Unresolved节点: {len(analysis['orphaned_unresolved'])}")
            print(f"  - 安全Unresolved节点: {len(analysis['safe_unresolved'])}")
            
            if analysis['orphaned_aliases']:
                print(f"\n🏷️ 孤岛Alias节点列表:")
                for alias in analysis['orphaned_aliases'][:10]:  # 显示前10个
                    print(f"  - {alias['alias_type']}: {alias['alias_value']}")
                if len(analysis['orphaned_aliases']) > 10:
                    print(f"  ... 还有 {len(analysis['orphaned_aliases']) - 10} 个")
            
            if analysis['orphaned_unresolved']:
                print(f"\n📄 孤岛Unresolved节点列表:")
                for unresolved in analysis['orphaned_unresolved'][:10]:  # 显示前10个
                    print(f"  - {unresolved['lid']}: {unresolved['title'][:50]}...")
                if len(analysis['orphaned_unresolved']) > 10:
                    print(f"  ... 还有 {len(analysis['orphaned_unresolved']) - 10} 个")
            
            if analysis['safe_unresolved']:
                print(f"\n✅ 安全Unresolved节点 (被多个文献引用):")
                for unresolved in analysis['safe_unresolved'][:5]:
                    print(f"  - {unresolved['lid']}: {unresolved['citing_count']} 引用 - {unresolved['title'][:50]}...")
            
            return stats
        
        # 实际删除
        async with self.driver.session() as session:
            # 删除孤岛Alias节点
            delete_alias_query = """
            MATCH (alias:Alias)
            WHERE NOT EXISTS((alias)-[:ALIAS_OF]->(:Literature))
            AND NOT EXISTS((alias)-[]->())
            AND NOT EXISTS(()-[]->(alias))
            DETACH DELETE alias
            RETURN count(alias) as deleted_count
            """
            
            result = await session.run(delete_alias_query)
            record = await result.single()
            stats["orphaned_aliases_deleted"] = record["deleted_count"] if record else 0
            
            # 删除孤岛Unresolved节点
            delete_unresolved_query = """
            MATCH (unresolved:Unresolved)
            WHERE NOT EXISTS((:Literature)-[:CITES]->(unresolved))
            DETACH DELETE unresolved
            RETURN count(unresolved) as deleted_count
            """
            
            result = await session.run(delete_unresolved_query)
            record = await result.single()
            stats["orphaned_unresolved_deleted"] = record["deleted_count"] if record else 0
            
            print(f"✅ 清理完成:")
            print(f"  - 删除孤岛Alias节点: {stats['orphaned_aliases_deleted']}")
            print(f"  - 删除孤岛Unresolved节点: {stats['orphaned_unresolved_deleted']}")
            
            return stats


async def main():
    parser = argparse.ArgumentParser(description="清理Neo4j数据库中的孤岛节点")
    parser.add_argument("--dry-run", action="store_true", 
                       help="只分析不删除，显示将要删除的节点")
    parser.add_argument("--verbose", action="store_true", 
                       help="显示详细信息")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    
    print("🧹 Neo4j 孤岛节点清理工具")
    print("=" * 50)
    
    cleaner = OrphanedNodeCleaner(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        # 首先检查数据库连接
        print("🔗 连接到 Neo4j 数据库...")
        
        # 执行清理或分析
        stats = await cleaner.clean_orphaned_nodes(dry_run=args.dry_run)
        
        if not args.dry_run:
            print("\n🎉 清理操作完成！")
            print("建议运行 --dry-run 模式验证当前状态。")
        else:
            print("\n💡 如需执行实际清理，请运行:")
            print("    python3 cleanup_orphaned_nodes.py")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    finally:
        await cleaner.close()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
