#!/usr/bin/env python3
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db import neo4j as neo4j_db

async def check_existing():
    try:
        # 创建连接 - create_task_connection 返回 (driver, driver) 元组
        driver_tuple = await neo4j_db.create_task_connection()
        driver = driver_tuple[0]  # 取第一个driver
        dao = LiteratureDAO(database=driver)
        
        # 查找包含 'Attention is All you Need' 的文献
        results = await dao.find_by_title_fuzzy('Attention is All you Need', limit=10)
        
        print(f'找到 {len(results)} 个匹配的文献:')
        for i, lit in enumerate(results):
            print(f'\n=== 文献 {i+1} ===')
            print(f'LID: {lit.lid}')
            print(f'标题: {lit.metadata.title if lit.metadata else "无元数据"}')
            if lit.metadata and lit.metadata.authors:
                print(f'作者: {[author.name for author in lit.metadata.authors[:5]]}')
            print(f'年份: {lit.metadata.year if lit.metadata else "无"}')
            
        # 关闭连接
        await neo4j_db.close_task_connection(driver)
        
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_existing())
