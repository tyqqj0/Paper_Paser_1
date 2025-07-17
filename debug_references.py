#!/usr/bin/env python3
"""调试references获取和转换"""

import asyncio
import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

from services.semantic_scholar import SemanticScholarClient
from models.literature import IdentifiersModel

async def debug_references():
    """调试references获取"""
    print("=== 调试References获取 ===")
    
    # 使用已知的DOI
    test_doi = "10.48550/arXiv.1706.03762"  # Attention is All You Need
    print(f"测试DOI: {test_doi}")
    
    try:
        # 1. 测试Semantic Scholar API
        print("\n1. 测试Semantic Scholar API...")
        client = SemanticScholarClient()
        
        # 直接调用API
        raw_refs = client.get_references(test_doi, limit=3)
        print(f"API返回的原始references数量: {len(raw_refs)}")
        
        if raw_refs:
            print("\n原始API返回的数据结构:")
            print(json.dumps(raw_refs[0], indent=2, ensure_ascii=False))
            
            # 2. 测试转换函数
            print("\n2. 测试转换函数...")
            
            # 导入转换函数
            from worker.tasks import convert_semantic_scholar_references
            
            # 模拟API返回的数据结构
            mock_api_data = []
            for ref in raw_refs:
                mock_api_data.append({
                    "citedPaper": ref  # 这是API实际返回的结构
                })
            
            converted_refs = convert_semantic_scholar_references(mock_api_data)
            print(f"转换后的references数量: {len(converted_refs)}")
            
            if converted_refs:
                print("\n转换后的第一个reference:")
                first_ref = converted_refs[0]
                print(f"Raw text: {first_ref.raw_text}")
                print(f"Source: {first_ref.source}")
                print(f"Parsed: {first_ref.parsed}")
                
        else:
            print("❌ API没有返回references数据")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug_references()) 