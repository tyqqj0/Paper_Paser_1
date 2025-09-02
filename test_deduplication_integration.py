#!/usr/bin/env python3
"""
测试集成的去重逻辑，检查修复后的标题和作者匹配是否正常工作
"""

import asyncio
import sys
import os
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from literature_parser_backend.worker.execution.data_pipeline import DataPipeline
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.models.literature import MetadataModel

async def test_deduplication():
    """测试去重逻辑"""
    print("=" * 60)
    print("测试集成去重逻辑")
    print("=" * 60)
    
    # 创建数据管道实例
    dao = LiteratureDAO()
    pipeline = DataPipeline(dao)
    
    # 模拟第一篇论文的元数据（已存在于数据库中）
    metadata1 = MetadataModel(
        title="Attention Is All You Need",
        authors=[
            {"name": "Ashish Vaswani"},
            {"name": "Noam Shazeer"},
            {"name": "Niki Parmar"},
            {"name": "Jakob Uszkoreit"},
            {"name": "Llion Jones"}
        ],
        year=2017,
        journal="NIPS"
    )
    
    # 模拟第二篇论文的元数据（不同格式的相同论文）
    metadata2 = MetadataModel(
        title="Attention is All you Need",  # 微小的大小写差异
        authors=[
            {"name": "Vaswani, Ashish"},  # "姓, 名" 格式
            {"name": "Shazeer, Noam"},
            {"name": "Parmar, Niki"},
            {"name": "Uszkoreit, Jakob"},
            {"name": "Jones, Llion"}
        ],
        year=2017,
        journal="NIPS"
    )
    
    print("\n📋 测试数据:")
    print("-" * 40)
    print(f"文献1 标题: {metadata1.title}")
    print(f"文献1 作者: {[author['name'] for author in metadata1.authors]}")
    print(f"文献2 标题: {metadata2.title}")
    print(f"文献2 作者: {[author['name'] for author in metadata2.authors]}")
    
    try:
        # 测试去重检查
        print("\n🔍 执行去重检查:")
        print("-" * 40)
        
        result = await pipeline._check_duplicate_literature(metadata2)
        
        print(f"\n🎯 去重检查结果:")
        print("-" * 40)
        print(f"是否重复: {result.get('is_duplicate', False)}")
        
        if result.get('is_duplicate'):
            print(f"已存在 LID: {result.get('existing_lid')}")
            print(f"重复原因: {result.get('reason')}")
            print("✅ 成功检测到重复文献!")
        else:
            print("❌ 未检测到重复，可能存在问题")
            
        # 额外测试：直接测试标题和作者匹配
        print(f"\n🔧 详细匹配测试:")
        print("-" * 40)
        
        title_match = pipeline._is_title_match(metadata1.title, metadata2.title)
        print(f"标题匹配: {'✅' if title_match else '❌'}")
        
        author_match = pipeline._is_author_match(metadata1.authors, metadata2.authors)
        print(f"作者匹配: {'✅' if author_match else '❌'}")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

async def test_fuzzy_search():
    """测试模糊搜索功能"""
    print("\n" + "=" * 60)
    print("测试模糊搜索功能")
    print("=" * 60)
    
    dao = LiteratureDAO()
    
    try:
        # 测试不同的标题变体
        test_titles = [
            "Attention Is All You Need",
            "Attention is All you Need", 
            "attention is all you need",
            "ATTENTION IS ALL YOU NEED"
        ]
        
        for title in test_titles:
            print(f"\n🔍 搜索标题: {title}")
            results = await dao.find_by_title_fuzzy(title, limit=3)
            print(f"找到 {len(results)} 个结果:")
            
            for result in results:
                if result and result.metadata:
                    print(f"  - LID: {result.lid}")
                    print(f"    标题: {result.metadata.title}")
                    if hasattr(result.metadata, 'authors') and result.metadata.authors:
                        authors = [author.get('name', '') if isinstance(author, dict) else str(author) 
                                 for author in result.metadata.authors[:3]]
                        print(f"    作者: {', '.join(authors)}...")
                    print()
            
    except Exception as e:
        print(f"❌ 搜索测试异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    await test_deduplication()
    await test_fuzzy_search()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
