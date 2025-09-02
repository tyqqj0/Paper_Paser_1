#!/usr/bin/env python3
"""
检查这些LID是否真的存在于数据库中
"""

import asyncio
import httpx

# 测试几个LID，包括真实存在的重复attention论文
TEST_LIDS = [
    "2017-ashish-aayn-fa59",   # Attention is All you Need (重复1)
    "2017-vaswani-aayn-9572",  # Attention Is All You Need (重复2) 
    "2020-dosovits-iwwtir-8421", # ViT论文
    "1992-polyak-asaa-c089",   # 优化论文
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
                    params={"lids": lid},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    nodes = data.get("nodes", [])
                    print(f"   📊 API响应: {len(nodes)} 个节点")
                    
                    if nodes:
                        for node in nodes:
                            title = node.get('title', 'No title')
                            print(f"   ✅ 找到: {node.get('lid')} - {title[:50]}...")
                    else:
                        print(f"   ⚠️ API正常但没有找到节点，LID可能不存在于数据库中")
                        # 显示完整响应以供调试
                        print(f"   🔍 完整响应: {data}")
                else:
                    print(f"   ❌ API错误: {response.status_code}")
                    error_text = response.text if hasattr(response, 'text') else 'No error details'
                    print(f"   📄 错误详情: {error_text[:100]}...")
                    
            except httpx.ConnectError as e:
                print(f"   🔌 连接错误: 无法连接到 {base_url} - {e}")
            except httpx.TimeoutException as e:
                print(f"   ⏰ 超时错误: {e}")
            except Exception as e:
                print(f"   💥 未知异常: {type(e).__name__}: {e}")
            
            print()

if __name__ == "__main__":
    asyncio.run(check_lids_exist())
