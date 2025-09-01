#!/usr/bin/env python3
"""
测试修复后的智能路由器 - 验证len()错误修复后是否能正常更新数据
"""

import sys
import asyncio
import logging
from literature_parser_backend.worker.execution.smart_router import SmartRouter
from literature_parser_backend.worker.metadata.base import IdentifierData
from literature_parser_backend.worker.metadata.registry import get_global_registry

async def test_smart_router_fix():
    """测试修复后的智能路由器"""
    print("=== 智能路由器修复测试 ===")
    
    # 启用详细日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    try:
        # 创建智能路由器
        router = SmartRouter()
        print(f"✅ 智能路由器创建成功: {router}")
        
        # 准备测试数据 - 使用之前成功的MLR论文URL
        url = "https://proceedings.mlr.press/v15/glorot11a.html"
        identifier_data = IdentifierData(url=url)
        
        print(f"\n🔍 测试URL: {url}")
        print("📋 开始处理...")
        
        # 执行智能路由处理
        result = await router.route_and_process(
            url=url,
            source_data={'url': url},
            task_id='test-fix-123'
        )
        
        print(f"\n📊 处理结果:")
        print(f"  状态: {result.get('status', 'unknown')}")
        print(f"  处理器: {result.get('processor_used', 'none')}")
        print(f"  解析分数: {result.get('parsing_score', 0)}")
        print(f"  是否完整: {result.get('is_complete', False)}")
        
        if result.get('metadata'):
            metadata = result['metadata']
            print(f"\n📖 元数据信息:")
            print(f"  标题: {metadata.get('title', 'N/A')}")
            print(f"  作者数: {len(metadata.get('authors', []))}")
            print(f"  年份: {metadata.get('year', 'N/A')}")
            print(f"  期刊: {metadata.get('venue', 'N/A')}")
            
        if result.get('new_identifiers'):
            print(f"\n🆔 新标识符: {result['new_identifiers']}")
            
        # 检查是否有错误
        if result.get('status') == 'failed':
            print(f"❌ 处理失败: {result.get('error_message', 'Unknown error')}")
            return False
        else:
            print(f"✅ 处理成功！没有len()错误")
            return True
            
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_smart_router_fix())
    print(f"\n=== 测试{'成功' if success else '失败'} ===")
    sys.exit(0 if success else 1)
