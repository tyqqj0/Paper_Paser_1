#!/usr/bin/env python3
"""
测试升级后的URL映射服务
验证多策略架构是否正常工作
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

from literature_parser_backend.services.url_mapper import get_url_mapping_service

async def test_url_mapping():
    """测试URL映射服务的多策略功能"""
    
    service = get_url_mapping_service()
    
    test_urls = [
        # IEEE URL - 我们的重点测试
        "https://ieeexplore.ieee.org/document/10000001",
        
        # ArXiv URL - 验证现有功能
        "https://arxiv.org/abs/2402.14735",
        
        # Nature URL - 验证其他平台
        "https://www.nature.com/articles/nature12373",
        
        # CVF URL - 验证会议论文
        "http://openaccess.thecvf.com/content_cvpr_2017/papers/He_Mask_R-CNN_CVPR_2017_paper.pdf",
    ]
    
    print("🚀 测试升级后的URL映射服务")
    print("=" * 60)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n📋 测试 {i}: {url}")
        print("-" * 50)
        
        try:
            # 测试异步版本
            result = await service.map_url(url)
            
            print(f"✅ 映射成功:")
            print(f"   DOI: {result.doi}")
            print(f"   ArXiv ID: {result.arxiv_id}")
            print(f"   PDF URL: {result.pdf_url}")
            print(f"   Source Page: {result.source_page_url}")
            print(f"   Venue: {result.venue}")
            print(f"   Year: {result.year}")
            print(f"   Confidence: {result.confidence}")
            print(f"   Adapter: {result.source_adapter}")
            print(f"   Strategy: {result.strategy_used}")
            
            if result.doi or result.arxiv_id:
                print("🎉 成功提取标识符!")
            else:
                print("⚠️  未找到有效标识符")
                
        except Exception as e:
            print(f"❌ 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 测试完成")

def test_sync_compatibility():
    """测试同步兼容性"""
    print("\n🔄 测试同步兼容性")
    print("-" * 30)
    
    service = get_url_mapping_service()
    url = "https://arxiv.org/abs/2402.14735"
    
    try:
        result = service.map_url_sync(url)
        print(f"✅ 同步调用成功: DOI={result.doi}, ArXiv={result.arxiv_id}")
    except Exception as e:
        print(f"❌ 同步调用失败: {e}")

if __name__ == "__main__":
    # 测试异步功能
    asyncio.run(test_url_mapping())
    
    # 测试同步兼容性
    test_sync_compatibility()
