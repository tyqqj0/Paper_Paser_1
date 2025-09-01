#!/usr/bin/env python3
"""
多链接图解析测试 - 测试内部关系图API的多种组合
验证不同论文组合的内部引用关系
"""

import asyncio
import httpx
import json
from typing import List, Dict, Any

# 从最新测试结果中提取的真实LID数据
REAL_LIDS = {
    # AI基础模型
    "transformer": "2017-vaswani-aayn-6096",
    "vision_transformer": "2020-dosovits-iwwtir-e64e", 
    "bert": "2018-devlin-bptdbt-dbc3",
    "attention_neurips": "2017-ashish-aayn-d46b",
    
    # CNN架构
    "alexnet": "2017-krizhevs-icdcnn-c3e3",
    "resnet": "2015-he-drlir-8046",
    "yolo": "2015-redmon-yolour-73f1",
    "unet": "2015-ronneber-ncnbis-e42c",
    
    # 优化和基础技术
    "adam": "2014-kingma-amso-13cd",
    "batch_norm": "2015-ioffe-bnadnt-32fa",
    "word2vec": "2013-mikolov-eewrvs-2806",
    "seq2seq": "2014-sutskeve-sslnn-1fca",
    "lstm": "1997-hochreit-lstm-59a8",
    
    # 经典论文
    "gan": "2014-goodfell-gan-4913",
    "alphago": "2016-silver-mgdnnt-ac1b",
    "lecun_dl": "2015-lecun-dl-9d4b",
    "polyak": "1992-polyak-asaa-9e1c",
    
    # 应用和其他
    "acm_paper": "2019-do-gtpncr-af82",
    "ieee_paper": "2018-peng-jodant-1f30",
    "imagenet": "2017-krizhevs-icdcnn-3225",
    "relu_research": "2011-glorot-dsrnn-f3e7",
}

class MultiLinkGraphTester:
    """多链接图解析测试器"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000/api"
        self.test_results = []
    
    async def run_all_tests(self):
        """运行所有测试用例"""
        print("🕸️ 多链接图解析测试 - 调试版本")
        print("=" * 60)
        print(f"📊 可用论文: {len(REAL_LIDS)} 篇")
        print()
        
        # 先运行一个简单的测试来查看完整响应
        print("🔍 第一步：查看完整API响应")
        print("-" * 40)
        
        # 测试单个论文，显示完整响应
        await self._debug_single_response()
        
        print("\n" + "=" * 60)
        print("🧪 第二步：运行完整测试套件")
        print("=" * 60)
        
        test_cases = [
            {
                "name": "单个论文测试",
                "description": "测试单篇论文（应该有节点，无边）",
                "lids": ["transformer"],
                "expected_nodes": 1,
                "expected_edges": 0
            },
            {
                "name": "Transformer家族",
                "description": "测试Transformer相关论文的内部关系",
                "lids": ["transformer", "vision_transformer", "bert", "attention_neurips"],
                "expected_nodes": 4,
                "expected_edges": "未知"
            },
            {
                "name": "CNN经典架构",
                "description": "测试CNN发展历程中的关键论文",
                "lids": ["alexnet", "resnet", "yolo", "unet"],
                "expected_nodes": 4,
                "expected_edges": "未知"
            }
        ]
        
        async with httpx.AsyncClient() as client:
            for i, test_case in enumerate(test_cases, 1):
                await self._run_single_test(client, i, test_case)
                print()
        
        # 生成测试报告
        self._generate_report()
    
    async def _debug_single_response(self):
        """调试单个响应，显示完整内容"""
        print("🔍 调试单个论文响应...")
        
        # 使用一个简单的LID
        test_lid = REAL_LIDS["transformer"]
        print(f"📚 测试LID: {test_lid}")
        
        try:
            async with httpx.AsyncClient() as client:
                # 调用API
                response = await client.get(
                    f"{self.base_url}/graphs",
                    params={"lids": test_lid}
                )
                
                print(f"📡 HTTP状态码: {response.status_code}")
                print(f"📡 响应头: {dict(response.headers)}")
                
                if response.status_code == 200:
                    # 显示原始响应文本
                    raw_text = response.text
                    print(f"📄 原始响应文本:")
                    print(f"   {raw_text}")
                    
                    # 尝试解析JSON
                    try:
                        data = response.json()
                        print(f"\n🔍 解析后的JSON结构:")
                        print(f"   数据类型: {type(data)}")
                        print(f"   顶层键: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                        
                        if isinstance(data, dict):
                            for key, value in data.items():
                                print(f"   {key}: {type(value)} = {value}")
                        
                        # 特别检查metadata
                        metadata = data.get("metadata", {})
                        print(f"\n📊 Metadata详情:")
                        print(f"   metadata类型: {type(metadata)}")
                        if isinstance(metadata, dict):
                            for key, value in metadata.items():
                                print(f"   {key}: {type(value)} = {value}")
                        
                        # 检查nodes和edges
                        nodes = data.get("nodes", [])
                        edges = data.get("edges", [])
                        print(f"\n📚 Nodes详情:")
                        print(f"   nodes类型: {type(nodes)}")
                        print(f"   nodes长度: {len(nodes) if isinstance(nodes, list) else 'Not a list'}")
                        if isinstance(nodes, list) and nodes:
                            print(f"   第一个node: {nodes[0]}")
                        
                        print(f"\n🔗 Edges详情:")
                        print(f"   edges类型: {type(edges)}")
                        print(f"   edges长度: {len(edges) if isinstance(edges, list) else 'Not a list'}")
                        if isinstance(edges, list) and edges:
                            print(f"   第一个edge: {edges[0]}")
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON解析失败: {e}")
                        print(f"   响应内容: {raw_text[:200]}...")
                
                else:
                    print(f"❌ 请求失败: {response.status_code}")
                    print(f"   错误响应: {response.text}")
                    
        except Exception as e:
            print(f"💥 调试过程中发生异常: {e}")
    
    async def _run_single_test(self, client: httpx.AsyncClient, test_num: int, test_case: Dict[str, Any]):
        """运行单个测试用例"""
        print(f"🧪 测试 {test_num}: {test_case['name']}")
        print(f"   📝 描述: {test_case['description']}")
        print(f"   📊 论文数量: {len(test_case['lids'])}")
        
        # 转换LID名称为实际ID
        actual_lids = [REAL_LIDS[lid_name] for lid_name in test_case['lids']]
        lids_str = ",".join(actual_lids)
        
        print(f"   🔗 LID: {lids_str[:80]}{'...' if len(lids_str) > 80 else ''}")
        
        try:
            # 调用关系图API
            response = await client.get(
                f"{self.base_url}/graphs",
                params={"lids": lids_str}
            )
            
            result = {
                "test_name": test_case['name'],
                "status_code": response.status_code,
                "success": False,
                "nodes_count": 0,
                "edges_count": 0,
                "error": None
            }
            
            print(f"   📡 状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                metadata = data.get("metadata", {})
                
                nodes_count = metadata.get('total_nodes', 0)
                edges_count = metadata.get('total_edges', 0)
                
                result.update({
                    "success": True,
                    "nodes_count": nodes_count,
                    "edges_count": edges_count,
                    "api_version": metadata.get('api_version', 'N/A'),
                    "relationship_type": metadata.get('relationship_type', 'N/A')
                })
                
                print(f"   ✅ 成功!")
                print(f"     📊 节点数: {nodes_count} (期望: {test_case['expected_nodes']})")
                print(f"     🔗 边数: {edges_count} (期望: {test_case['expected_edges']})")
                print(f"     🔧 关系类型: {metadata.get('relationship_type', 'N/A')}")
                print(f"     📱 API版本: {metadata.get('api_version', 'N/A')}")
                
                # 显示节点详情
                nodes = data.get("nodes", [])
                if nodes:
                    print(f"     📚 节点详情:")
                    for j, node in enumerate(nodes[:5], 1):
                        title = node.get("title", "No title")
                        print(f"       {j}. {node.get('lid')}: {title[:40]}{'...' if len(title) > 40 else ''}")
                    if len(nodes) > 5:
                        print(f"       ... 还有 {len(nodes) - 5} 个节点")
                
                # 显示关系详情
                edges = data.get("edges", [])
                if edges:
                    print(f"     🔗 关系详情:")
                    for j, edge in enumerate(edges[:5], 1):
                        from_lid = edge.get('from_lid', 'N/A')
                        to_lid = edge.get('to_lid', 'N/A')
                        confidence = edge.get('confidence', 'N/A')
                        source = edge.get('source', 'N/A')
                        
                        # 转换LID为论文名称（如果可能）
                        from_name = self._lid_to_name(from_lid)
                        to_name = self._lid_to_name(to_lid)
                        
                        print(f"       {j}. {from_name} → {to_name}")
                        print(f"          置信度: {confidence}, 来源: {source}")
                    if len(edges) > 5:
                        print(f"       ... 还有 {len(edges) - 5} 个关系")
                else:
                    print(f"     ⚠️ 没有发现内部引用关系")
                
                # 验证期望结果
                if nodes_count == test_case['expected_nodes']:
                    print(f"     ✅ 节点数量符合期望")
                elif nodes_count == 0:
                    print(f"     ⚠️ 节点数为0，可能LID不存在于数据库")
                else:
                    print(f"     ❓ 节点数量与期望不符")
                    
            else:
                error_detail = response.text
                result["error"] = error_detail
                print(f"   ❌ 请求失败: {response.status_code}")
                print(f"     错误: {error_detail}")
            
            self.test_results.append(result)
            
        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            self.test_results.append(result)
            print(f"   💥 异常: {error_msg}")
    
    def _lid_to_name(self, lid: str) -> str:
        """将LID转换为论文名称"""
        for name, actual_lid in REAL_LIDS.items():
            if actual_lid == lid:
                return name
        return lid[:15] + "..."
    
    def _generate_report(self):
        """生成测试报告"""
        print("📋 测试报告总结")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r["success"])
        
        print(f"📊 总体统计:")
        print(f"   总测试数: {total_tests}")
        print(f"   成功测试: {successful_tests}")
        print(f"   成功率: {successful_tests/total_tests*100:.1f}%")
        
        # 统计节点和边
        total_nodes = sum(r["nodes_count"] for r in self.test_results if r["success"])
        total_edges = sum(r["edges_count"] for r in self.test_results if r["success"])
        
        print(f"   总节点数: {total_nodes}")
        print(f"   总边数: {total_edges}")
        
        print(f"\n📋 详细结果:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"   {status} {result['test_name']}")
            if result["success"]:
                print(f"      节点: {result['nodes_count']}, 边: {result['edges_count']}")
            else:
                print(f"      错误: {result.get('error', 'Unknown error')}")
        
        # 如果有关系数据，分析网络特征
        if total_edges > 0:
            print(f"\n🕸️ 网络分析:")
            print(f"   网络密度: 发现了 {total_edges} 个内部引用关系")
            print(f"   这说明这些论文之间确实存在引用关系！")
        else:
            print(f"\n💡 分析结论:")
            print(f"   虽然API正常工作，但没有发现内部引用关系")
            print(f"   可能原因:")
            print(f"   1. 这些论文之间确实没有直接引用关系")
            print(f"   2. 引用关系数据还没有被解析和保存")
            print(f"   3. 需要运行引用解析流程来建立关系")
            print(f"   4. 数据库查询逻辑有问题")
            print(f"   5. LID格式或存储方式不匹配")

async def main():
    """主函数"""
    tester = MultiLinkGraphTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
