#!/usr/bin/env python3

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/home/parser/code/Paper_Paser_1')

from literature_parser_backend.db.neo4j import Neo4jDriver
from literature_parser_backend.db.dao import LiteratureDAO

async def check_database_state():
    """检查数据库中所有Vaswani相关的文献"""
    
    # 初始化数据库连接
    driver = Neo4jDriver()
    await driver.connect()
    
    dao = LiteratureDAO(database=driver)
    
    try:
        # 获取所有文献
        all_lit = await dao.get_all_literature(limit=10)
        
        print(f"🔍 数据库中总共有 {len(all_lit)} 篇文献:")
        
        vaswani_papers = []
        for i, lit in enumerate(all_lit):
            if lit and lit.metadata:
                print(f"  {i+1}. LID: {lit.lid}")
                print(f"     标题: {lit.metadata.title}")
                print(f"     年份: {getattr(lit.metadata, 'year', 'N/A')}")
                print()
                
                # 如果包含Vaswani，添加到特殊列表
                if lit.metadata.title and 'attention' in lit.metadata.title.lower():
                    vaswani_papers.append(lit)
        
        print(f"🎯 发现 {len(vaswani_papers)} 篇Attention相关论文:")
        for paper in vaswani_papers:
            print(f"  - LID: {paper.lid}")
            print(f"    标题: {paper.metadata.title}")
            if hasattr(paper.metadata, 'authors') and paper.metadata.authors:
                authors = [auth.name for auth in paper.metadata.authors[:3]]
                print(f"    作者: {', '.join(authors)}...")
            print()
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        print(traceback.format_exc())
    
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(check_database_state())
