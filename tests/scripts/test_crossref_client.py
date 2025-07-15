#!/usr/bin/env python3
"""
测试 CrossRef API 客户端
"""
import asyncio
import json
from literature_parser_backend.services.crossref import CrossRefClient

async def test_crossref_client():
    """测试 CrossRef 客户端功能"""
    print("🔍 测试 CrossRef API 客户端...")
    print("=" * 50)
    
    client = CrossRefClient()
    
    # 测试 1: 通过 DOI 获取元数据
    print("\n📋 测试 1: 通过 DOI 获取元数据")
    test_doi = "10.1038/nature12373"
    print(f"测试 DOI: {test_doi}")
    
    try:
        metadata = await client.get_metadata_by_doi(test_doi)
        if metadata:
            print("✅ 成功获取元数据:")
            print(f"  标题: {metadata.get('title', 'N/A')}")
            print(f"  期刊: {metadata.get('journal', 'N/A')}")
            print(f"  年份: {metadata.get('year', 'N/A')}")
            print(f"  作者数量: {len(metadata.get('authors', []))}")
            if metadata.get('authors'):
                first_author = metadata['authors'][0]
                print(f"  第一作者: {first_author.get('family_name', '')}, {first_author.get('given_names', [])}")
        else:
            print("❌ 未找到元数据")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试 2: 搜索功能
    print("\n📋 测试 2: 通过标题搜索")
    test_title = "Attention Is All You Need"
    print(f"搜索标题: {test_title}")
    
    try:
        results = await client.search_by_title_author(test_title, limit=3)
        print(f"✅ 找到 {len(results)} 个结果:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result.get('title', 'N/A')} ({result.get('year', 'N/A')})")
    except Exception as e:
        print(f"❌ 搜索错误: {e}")
    
    # 测试 3: 检查 DOI 机构
    print("\n📋 测试 3: 检查 DOI 注册机构")
    try:
        agency = await client.check_doi_agency(test_doi)
        print(f"✅ DOI {test_doi} 的注册机构: {agency}")
    except Exception as e:
        print(f"❌ 检查机构错误: {e}")
    
    print("\n✅ CrossRef 客户端测试完成!")

if __name__ == "__main__":
    asyncio.run(test_crossref_client()) 