#!/usr/bin/env python3
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db import neo4j as neo4j_db

async def check_all_records():
    try:
        # 创建连接 - create_task_connection 返回 (driver, driver) 元组
        driver_tuple = await neo4j_db.create_task_connection()
        driver = driver_tuple[0]  # 取第一个driver
        dao = LiteratureDAO(database=driver)
        
        # 由于没有find_all方法，使用模糊搜索找一些记录
        # 先尝试几个常见的词来看数据库中有什么
        search_terms = ["the", "a", "an", "and", "of", "in", "to", "for", "with", "on"]
        results = []
        
        for term in search_terms:
            try:
                partial_results = await dao.find_by_title_fuzzy(term, limit=5)
                results.extend(partial_results)
                if len(results) >= 10:  # 限制到10个结果
                    results = results[:10]
                    break
            except Exception as e:
                print(f"搜索词 '{term}' 失败: {e}")
                continue
        
        print(f'数据库中总共有 {len(results)} 个文献记录:')
        
        if not results:
            print('数据库中没有任何文献记录')
        else:
            for i, lit in enumerate(results):
                print(f'\n=== 文献 {i+1} ===')
                print(f'LID: {lit.lid}')
                if lit.metadata:
                    print(f'标题: {lit.metadata.title}')
                    if lit.metadata.authors:
                        author_names = [author.name for author in lit.metadata.authors[:3]]
                        print(f'作者前3个: {author_names}')
                    print(f'年份: {lit.metadata.year}')
                    print(f'DOI: {lit.metadata.doi}')
                else:
                    print('没有元数据')
            
        # 关闭连接
        await neo4j_db.close_task_connection(driver)
        
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_all_records())
