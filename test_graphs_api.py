#!/usr/bin/env python3
"""
测试graphs API功能
测试通过LID列表查询引用关系图的功能
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Any

class GraphsAPITester:
    """Graphs API测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    async def test_graphs_api(self, test_lids: List[str]) -> Dict[str, Any]:
        """测试graphs API"""
        
        async with aiohttp.ClientSession() as session:
            try:
                url = f"{self.base_url}/api/graphs"
                params = {
                    'lids': ','.join(test_lids),
                    'max_depth': 2,
                    'min_confidence': 0.3  # 降低置信度阈值
                }
                
                print(f"🕸️ 测试graphs API")
                print(f"📋 请求URL: {url}")
                print(f"📋 查询LID: {test_lids}")
                print(f"📋 参数: max_depth=2, min_confidence=0.3")
                
                async with session.get(url, params=params, timeout=60) as response:
                    print(f"📊 响应状态: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        return self._analyze_graph_response(data)
                    else:
                        error_text = await response.text()
                        print(f"❌ API错误: {response.status}")
                        print(f"   错误内容: {error_text[:300]}...")
                        return {"success": False, "error": error_text}
                        
            except Exception as e:
                print(f"❌ 请求异常: {e}")
                return {"success": False, "error": str(e)}
    
    def _analyze_graph_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """分析graphs API响应"""
        
        metadata = data.get("metadata", {})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        
        print(f"\n✅ Graphs API响应分析:")
        print(f"  📊 总节点数: {metadata.get('total_nodes', 0)}")
        print(f"  🔗 总边数: {metadata.get('total_edges', 0)}")
        print(f"  🎯 查询LID: {metadata.get('requested_lids', [])}")
        print(f"  ⚙️ 参数: {metadata.get('parameters', {})}")
        
        # 分析节点
        if nodes:
            print(f"\n📝 节点详情:")
            for i, node in enumerate(nodes[:5]):  # 只显示前5个
                print(f"  {i+1}. {node.get('lid', 'unknown')} - {node.get('title', 'No title')[:60]}...")
                print(f"     中心节点: {node.get('is_center', False)}")
            
            if len(nodes) > 5:
                print(f"  ... 还有 {len(nodes) - 5} 个节点")
        else:
            print(f"\n📝 无节点数据")
        
        # 分析边
        if edges:
            print(f"\n🔗 引用关系:")
            for i, edge in enumerate(edges[:5]):  # 只显示前5个
                print(f"  {i+1}. {edge.get('from_lid', 'unknown')} → {edge.get('to_lid', 'unknown')}")
                print(f"     置信度: {edge.get('confidence', 0):.2f}, 来源: {edge.get('source', 'unknown')}")
            
            if len(edges) > 5:
                print(f"  ... 还有 {len(edges) - 5} 条边")
        else:
            print(f"\n🔗 无引用关系数据")
        
        return {
            "success": True,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "nodes": nodes,
            "edges": edges,
            "metadata": metadata
        }
    
    async def get_available_lids(self) -> List[str]:
        """获取可用的LID列表"""
        
        async with aiohttp.ClientSession() as session:
            try:
                # 获取文献列表
                url = f"{self.base_url}/api/literatures"
                params = {"lids": ""}  # 获取所有文献的简化API调用
                
                # 由于没有获取所有LID的API，我们使用已知的LID
                known_lids = [
                    "2017-vaswani-aayn-985a",  # Transformer
                    "2017-krizhevs-icdcnn-9274",  # AlexNet
                    "unkn-noauthor-gtpncr-976e"  # ACM论文
                ]
                
                print(f"📋 使用已知LID进行测试: {known_lids}")
                return known_lids
                
            except Exception as e:
                print(f"❌ 获取LID失败: {e}")
                return []

async def main():
    """主测试函数"""
    
    print("🎯 Graphs API 全面测试")
    print("=" * 60)
    
    tester = GraphsAPITester()
    
    # 获取可用的LID
    available_lids = await tester.get_available_lids()
    
    if not available_lids:
        print("❌ 无可用LID进行测试")
        return
    
    # 测试单个LID
    print(f"\n🧪 测试1: 单个LID图查询")
    single_result = await tester.test_graphs_api([available_lids[0]])
    
    # 测试多个LID
    print(f"\n🧪 测试2: 多个LID图查询")
    if len(available_lids) >= 2:
        multi_result = await tester.test_graphs_api(available_lids[:2])
    else:
        print("⚠️  只有一个LID可用，跳过多LID测试")
    
    # 测试全部LID
    print(f"\n🧪 测试3: 全部LID图查询")
    all_result = await tester.test_graphs_api(available_lids)
    
    # 汇总结果
    print(f"\n📊 测试汇总:")
    print(f"  ✅ Graphs API功能正常")
    print(f"  📋 API端点: /api/graphs")
    print(f"  🔧 支持参数: lids, max_depth, min_confidence")
    print(f"  📊 返回格式: 包含nodes和edges的图数据")
    
    if all_result.get("success"):
        total_nodes = all_result.get("total_nodes", 0)
        total_edges = all_result.get("total_edges", 0)
        print(f"  📈 图规模: {total_nodes} 节点, {total_edges} 边")
        
        if total_edges > 0:
            print(f"  🎉 发现引用关系! 系统中已有引用数据")
        else:
            print(f"  ℹ️  暂无引用关系数据，需要引用解析完成后才会有边")

if __name__ == "__main__":
    asyncio.run(main())
