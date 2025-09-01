#!/usr/bin/env python3
"""
检查这些LID是否真的存在于数据库中
"""

import asyncio
import httpx

# 测试几个LID
TEST_LIDS = [
    "2017-vaswani-aayn-6096",
    "2020-dosovits-iwwtir-e64e", 
    "2015-he-drlir-8046",
]

async def check_lids_exist():
    """检查LID是否存在"""
    print("🔍 检查LID是否存在于数据库中")
    print("=" * 50)
    
    base_url = "http://localhost:8000/api"
    
    async with httpx.AsyncClient() as client:
        for i, lid in enumerate(TEST_LIDS, 1):
            print(f"{i}. 检查 LID: {lid}")
            
            try:
                # 尝试通过graphs API检查（即使没有关系，也应该返回节点）
                response = await client.get(
                    f"{base_url}/graphs",
                    params={"lids": lid}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    nodes = data.get("nodes", [])
                    print(f"   📊 API响应: {len(nodes)} 个节点")
                    
                    if nodes:
                        for node in nodes:
                            print(f"   ✅ 找到: {node.get('lid')} - {node.get('title', 'No title')[:50]}...")
                    else:
                        print(f"   ⚠️ API正常但没有找到节点，可能LID不存在于数据库")
                else:
                    print(f"   ❌ API错误: {response.status_code}")
                    
            except Exception as e:
                print(f"   💥 异常: {e}")
            
            print()

if __name__ == "__main__":
    asyncio.run(check_lids_exist())
