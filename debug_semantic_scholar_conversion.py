#!/usr/bin/env python3
"""
调试Semantic Scholar元数据转换问题
"""

import os
import sys
import asyncio
import json
from typing import Dict, Any

# 添加项目路径
sys.path.insert(0, '/home/parser/code/Paper_Paser_1')

from literature_parser_backend.services.semantic_scholar import SemanticScholarClient
from literature_parser_backend.worker.metadata.processors.semantic_scholar import SemanticScholarProcessor
from literature_parser_backend.models.identifiers import IdentifierData

async def debug_conversion():
    """调试DOI转换过程"""
    
    # 测试的DOI
    test_doi = "10.1000/182"
    
    print(f"🔍 调试DOI: {test_doi}")
    print("=" * 50)
    
    # 1. 测试Semantic Scholar客户端直接调用
    print("1. 测试Semantic Scholar客户端...")
    client = SemanticScholarClient()
    
    raw_data = client.get_metadata(test_doi, id_type="doi")
    print(f"✅ 原始数据获取成功: {bool(raw_data)}")
    
    if raw_data:
        print("📋 原始数据结构:")
        print(f"  - title: {raw_data.get('title')}")
        print(f"  - authors: {raw_data.get('authors')}")
        print(f"  - year: {raw_data.get('year')}")
        print(f"  - venue: {raw_data.get('venue')}")
        
        # 保存完整原始数据用于分析
        with open("/tmp/s2_raw_data.json", "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"💾 完整原始数据已保存到: /tmp/s2_raw_data.json")
    
    print("\n" + "=" * 50)
    
    # 2. 测试Semantic Scholar处理器
    print("2. 测试Semantic Scholar处理器...")
    
    processor = SemanticScholarProcessor()
    
    # 创建标识符数据
    identifier_data = IdentifierData(doi=test_doi)
    
    # 调用处理器
    result = await processor.process(identifier_data)
    
    print(f"✅ 处理器结果: {result.success}")
    
    if result.success and result.metadata:
        metadata = result.metadata
        print("📊 转换后的元数据:")
        print(f"  - title: {metadata.title}")
        print(f"  - authors: {len(metadata.authors)} 个作者")
        for i, author in enumerate(metadata.authors):
            print(f"    {i+1}. {author.name} (ID: {getattr(author, 's2_id', 'N/A')})")
        print(f"  - year: {metadata.year}")
        print(f"  - journal: {metadata.journal}")
        print(f"  - abstract: {metadata.abstract[:100] if metadata.abstract else None}...")
    
    else:
        print(f"❌ 处理失败: {result.error}")
    
    print("\n" + "=" * 50)
    
    # 3. 手动测试转换函数
    print("3. 手动测试转换函数...")
    
    if raw_data:
        metadata = processor._convert_semantic_scholar_to_metadata(raw_data)
        print(f"📊 手动转换结果:")
        print(f"  - title: {metadata.title}")
        print(f"  - authors: {len(metadata.authors)} 个作者")
        for i, author in enumerate(metadata.authors):
            print(f"    {i+1}. {author.name} (ID: {getattr(author, 's2_id', 'N/A')})")
        print(f"  - year: {metadata.year}")
        print(f"  - journal: {metadata.journal}")
    
    print("\n" + "=" * 50)
    print("✅ 调试完成")

if __name__ == "__main__":
    asyncio.run(debug_conversion())
