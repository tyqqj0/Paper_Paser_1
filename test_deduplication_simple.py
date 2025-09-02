#!/usr/bin/env python3
"""
简化的去重逻辑测试，不依赖数据库连接
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from literature_parser_backend.worker.execution.data_pipeline import DataPipeline
from literature_parser_backend.models.literature import MetadataModel, AuthorModel

def test_title_and_author_matching():
    """测试标题和作者匹配逻辑"""
    print("=" * 60)
    print("测试标题和作者匹配逻辑")
    print("=" * 60)
    
    # 创建数据管道实例（不需要DAO）
    pipeline = DataPipeline(None)
    
    # 模拟第一篇论文的元数据（已存在于数据库中）
    metadata1 = MetadataModel(
        title="Attention Is All You Need",
        authors=[
            AuthorModel(name="Ashish Vaswani"),
            AuthorModel(name="Noam Shazeer"),
            AuthorModel(name="Niki Parmar"),
            AuthorModel(name="Jakob Uszkoreit"),
            AuthorModel(name="Llion Jones")
        ],
        year=2017,
        journal="NIPS"
    )
    
    # 模拟第二篇论文的元数据（不同格式的相同论文）
    metadata2 = MetadataModel(
        title="Attention is All you Need",  # 微小的大小写差异
        authors=[
            AuthorModel(name="Vaswani, Ashish"),  # "姓, 名" 格式
            AuthorModel(name="Shazeer, Noam"),
            AuthorModel(name="Parmar, Niki"),
            AuthorModel(name="Uszkoreit, Jakob"),
            AuthorModel(name="Jones, Llion")
        ],
        year=2017,
        journal="NIPS"
    )
    
    print("\n📋 测试数据:")
    print("-" * 40)
    print(f"文献1 标题: {metadata1.title}")
    print(f"文献1 作者: {[author.name for author in metadata1.authors]}")
    print(f"文献2 标题: {metadata2.title}")
    print(f"文献2 作者: {[author.name for author in metadata2.authors]}")
    
    try:
        # 测试标题匹配
        print("\n🔍 标题匹配测试:")
        print("-" * 40)
        title_match = pipeline._is_title_match(metadata1.title, metadata2.title)
        print(f"标题匹配结果: {'✅ 匹配' if title_match else '❌ 不匹配'}")
        
        # 测试作者匹配
        print("\n👥 作者匹配测试:")
        print("-" * 40)
        author_match = pipeline._is_author_match(metadata1.authors, metadata2.authors)
        print(f"作者匹配结果: {'✅ 匹配' if author_match else '❌ 不匹配'}")
        
        # 综合结果
        print(f"\n🎯 综合结果:")
        print("-" * 40)
        print(f"标题匹配: {'✅' if title_match else '❌'}")
        print(f"作者匹配: {'✅' if author_match else '❌'}")
        
        if title_match and author_match:
            print("🔄 结论: 这两篇论文应该被检测为重复!")
            return True
        else:
            print("🆕 结论: 这两篇论文不会被检测为重复")
            if not title_match:
                print("   - 标题匹配失败")
            if not author_match:
                print("   - 作者匹配失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("测试边界情况")
    print("=" * 60)
    
    pipeline = DataPipeline(None)
    
    # 测试案例1：完全不同的论文
    metadata_different1 = MetadataModel(
        title="Deep Learning",
        authors=[AuthorModel(name="Ian Goodfellow")],
        year=2016
    )
    
    metadata_different2 = MetadataModel(
        title="Machine Learning Yearning",
        authors=[AuthorModel(name="Andrew Ng")],
        year=2018
    )
    
    print("\n🧪 测试案例1：完全不同的论文")
    print("-" * 40)
    title_match = pipeline._is_title_match(metadata_different1.title, metadata_different2.title)
    author_match = pipeline._is_author_match(metadata_different1.authors, metadata_different2.authors)
    print(f"标题匹配: {'✅' if title_match else '❌'} (期望: ❌)")
    print(f"作者匹配: {'✅' if author_match else '❌'} (期望: ❌)")
    
    # 测试案例2：相同标题不同作者
    metadata_same_title1 = MetadataModel(
        title="Introduction to Machine Learning",
        authors=[AuthorModel(name="Tom Mitchell")],
        year=1997
    )
    
    metadata_same_title2 = MetadataModel(
        title="Introduction to Machine Learning",
        authors=[AuthorModel(name="Ethem Alpaydin")],
        year=2004
    )
    
    print("\n🧪 测试案例2：相同标题不同作者")
    print("-" * 40)
    title_match = pipeline._is_title_match(metadata_same_title1.title, metadata_same_title2.title)
    author_match = pipeline._is_author_match(metadata_same_title1.authors, metadata_same_title2.authors)
    print(f"标题匹配: {'✅' if title_match else '❌'} (期望: ✅)")
    print(f"作者匹配: {'✅' if author_match else '❌'} (期望: ❌)")
    print(f"综合判断: 不应被视为重复 (需要标题+作者都匹配)")

def main():
    """主测试函数"""
    success = test_title_and_author_matching()
    test_edge_cases()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if success:
        print("✅ 主要测试通过：修复后的去重逻辑能够正确识别重复文献")
        print("🔧 建议：可以对数据库中的现有文献应用这个去重逻辑")
    else:
        print("❌ 主要测试失败：去重逻辑仍需要进一步调试")
    
    print("\n📝 下一步行动:")
    print("1. 如果测试通过，可以编写脚本来清理数据库中的重复文献")
    print("2. 如果测试失败，需要进一步调试匹配逻辑")

if __name__ == "__main__":
    main()
