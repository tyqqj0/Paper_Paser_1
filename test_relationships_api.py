#!/usr/bin/env python3
"""
测试文献关系图API端点
"""

import asyncio
import httpx
import json
from datetime import datetime

async def test_relationships_api():
    """测试关系图API"""
    print("🔗 测试文献关系图API")
    print("=" * 60)
    
    base_url = "http://localhost:8000/api"
    
    async with httpx.AsyncClient() as client:
        
        # 1. 首先查看数据库中有哪些文献
        print("📋 1. 查询现有文献...")
        try:
            # 这可能不存在，但先试试
            response = await client.get(f"{base_url}/literature/")
            if response.status_code == 200:
                literatures = response.json()
                print(f"   找到 {len(literatures.get('items', []))} 篇文献")
                
                # 显示前几篇的LID
                for i, lit in enumerate(literatures.get('items', [])[:5]):
                    print(f"   {i+1}. LID: {lit.get('lid', 'N/A')} - {lit.get('metadata', {}).get('title', 'No title')[:50]}...")
                    
            else:
                print(f"   ❌ 无法查询文献列表: {response.status_code}")
        except Exception as e:
            print(f"   ⚠️ 查询文献列表失败: {e}")
        
        print()
        
        # 2. 测试关系图API - 先用假数据测试API是否工作
        print("🕸️ 2. 测试关系图API...")
        
        test_cases = [
            {
                "name": "单个LID测试",
                "lids": "test-lid-001",
                "max_depth": 1,
                "min_confidence": 0.5
            },
            {
                "name": "多个LID测试", 
                "lids": "test-lid-001,test-lid-002",
                "max_depth": 2,
                "min_confidence": 0.3
            },
            {
                "name": "高置信度测试",
                "lids": "test-lid-001",
                "max_depth": 1,
                "min_confidence": 0.8
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"   测试 {i}: {test_case['name']}")
            
            try:
                params = {
                    "lids": test_case["lids"],
                    "max_depth": test_case["max_depth"], 
                    "min_confidence": test_case["min_confidence"]
                }
                
                response = await client.get(f"{base_url}/graphs", params=params)
                
                print(f"     状态码: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"     节点数: {data.get('metadata', {}).get('total_nodes', 0)}")
                    print(f"     边数: {data.get('metadata', {}).get('total_edges', 0)}")
                    print(f"     API版本: {data.get('metadata', {}).get('api_version', 'N/A')}")
                    
                    # 显示一些细节
                    nodes = data.get('nodes', [])
                    edges = data.get('edges', [])
                    
                    if nodes:
                        print(f"     节点示例: {nodes[0]}")
                    if edges:
                        print(f"     边示例: {edges[0]}")
                        
                elif response.status_code == 400:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"     ⚠️ 客户端错误: {error_detail}")
                elif response.status_code == 500:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"     ❌ 服务器错误: {error_detail}")
                else:
                    print(f"     ❓ 未知响应: {response.text}")
                    
            except Exception as e:
                print(f"     💥 请求异常: {e}")
                
            print()
        
        # 3. 测试参数验证
        print("🔍 3. 测试参数验证...")
        
        validation_tests = [
            {
                "name": "空LID列表",
                "params": {"lids": ""},
                "expected": 400
            },
            {
                "name": "过多LID",
                "params": {"lids": ",".join([f"test-{i}" for i in range(25)])},
                "expected": 400
            },
            {
                "name": "无效深度",
                "params": {"lids": "test-001", "max_depth": 10},
                "expected": 422  # FastAPI validation error
            },
            {
                "name": "无效置信度",
                "params": {"lids": "test-001", "min_confidence": 1.5},
                "expected": 422
            }
        ]
        
        for test in validation_tests:
            print(f"   测试: {test['name']}")
            try:
                response = await client.get(f"{base_url}/graphs", params=test["params"])
                print(f"     状态码: {response.status_code} (期望: {test['expected']})")
                
                if response.status_code != test["expected"]:
                    print(f"     ⚠️ 状态码不匹配！")
                    print(f"     响应: {response.text}")
                else:
                    print(f"     ✅ 验证通过")
                    
            except Exception as e:
                print(f"     💥 请求异常: {e}")
            print()
        
        print("🎯 关系图API测试完成！")

if __name__ == "__main__":
    asyncio.run(test_relationships_api())
