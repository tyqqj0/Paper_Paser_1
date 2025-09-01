#!/usr/bin/env python3
"""
测试修复后的数据传递逻辑
验证：后续处理器能接收到前面处理器解析的title和authors信息
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

from worker.execution.smart_router import SmartRouter
from worker.metadata.registry import MetadataProcessorRegistry
from worker.metadata.base import IdentifierData

async def test_data_passing():
    """测试处理器间数据传递"""
    print("🧪 测试处理器间数据传递...")
    
    # 初始化
    registry = MetadataProcessorRegistry()
    router = SmartRouter(registry)
    
    # 测试用例：MLR Press URL（Site Parser V2应该能解析出title和authors）
    test_data = {
        "url": "https://proceedings.mlr.press/v15/glorot11a.html"
    }
    
    print(f"\n📋 测试用例: MLR Press URL")
    print(f"输入: {test_data}")
    print(f"期望: Site Parser V2 解析出title和authors，后续处理器能接收到这些信息")
    
    try:
        result = await router.route_and_process(test_data)
        
        print(f"\n📊 结果分析:")
        print(f"- 成功: {result.get('success', False)}")
        print(f"- 主处理器: {result.get('processor_used', 'unknown')}")
        print(f"- 解析分数: {result.get('parsing_score', 0.0):.3f}")
        print(f"- 置信度: {result.get('confidence', 0.0):.3f}")
        print(f"- 尝试的处理器: {result.get('attempted_processors', [])}")
        
        # 检查metadata内容
        if 'metadata' in result:
            metadata = result['metadata']
            print(f"\n📝 解析出的Metadata:")
            print(f"- 标题: {metadata.get('title', 'N/A')}")
            print(f"- 作者: {metadata.get('authors', 'N/A')}")
            print(f"- 年份: {metadata.get('year', 'N/A')}")
            print(f"- 期刊/会议: {metadata.get('venue', 'N/A')}")
        
        # 检查累积统计
        if 'accumulation_summary' in result:
            summary = result['accumulation_summary']
            print(f"\n📈 累积统计:")
            print(f"- 总metadata字段: {summary['total_metadata_fields']}")
            print(f"- 总identifiers: {summary['total_identifiers']}")
            print(f"- 贡献处理器: {summary['contributing_processors']}")
        
        # 检查metadata来源
        if 'metadata_sources' in result:
            print(f"\n🔍 Metadata来源分析:")
            sources = result['metadata_sources']
            for field, source_info in sources.items():
                print(f"- {field}: {source_info.get('source_processor', 'unknown')}")
                
        print(f"\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_data_passing())
