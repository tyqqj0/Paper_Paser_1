#!/usr/bin/env python3
"""
调试第二次去重为什么没有触发
"""

import asyncio
import logging
from literature_parser_backend.worker.tasks import process_literature_task
from literature_parser_backend.worker.celery_app import celery_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """测试第二次去重的触发条件"""
    
    # 模拟第二次提交同一个DOI
    test_data = {
        'identifiers': {'doi': '10.48550/arXiv.1706.03762'}, 
        'title': 'Processing...'
    }
    
    print("🔍 调试第二次去重触发条件")
    print(f"📋 测试数据: {test_data}")
    
    # 检查路由判断
    from literature_parser_backend.worker.execution.routing import RouteManager
    
    route_manager = RouteManager.get_instance()
    
    # 检查是否有URL
    url = test_data.get('url', '')
    print(f"📋 URL字段: '{url}'")
    
    if url:
        route = route_manager.determine_route(url)
        print(f"📋 路由结果: {route.name if route else 'None'}")
        
        if route and route.name != "standard_waterfall":
            print("✅ 会启用智能路由，第二次去重会触发")
        else:
            print("❌ 不会启用智能路由，第二次去重不会触发")
    else:
        print("❌ 没有URL，不会启用智能路由，第二次去重不会触发")
    
    print("\n🔧 问题分析:")
    print("1. 第二次去重只在智能路由完成时触发 (tasks.py:928-942)")
    print("2. 智能路由只在有URL且能匹配到专门路由时启用")
    print("3. 纯DOI提交没有URL，不会启用智能路由")
    print("4. 因此第二次去重不会触发")
    
    print("\n💡 解决方案:")
    print("需要在传统流程中也添加第二次去重检查")

if __name__ == "__main__":
    asyncio.run(main())
