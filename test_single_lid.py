#!/usr/bin/env python3
"""
测试单个LID在关系图API中的响应
"""

import asyncio
import httpx

async def test_single_lid():
    """测试单个LID"""
    print("🔍 测试单个LID - 调试节点查询")
    print("=" * 40)
    
    # 使用最新测试成功的LID
    test_lid = "2017-vaswani-aayn-6096"  # Transformer论文
    
    base_url = "http://localhost:8000/api"
    
    async with httpx.AsyncClient() as client:
        print(f"📚 测试LID: {test_lid}")
        
        try:
            response = await client.get(
                f"{base_url}/graphs",
                params={"lids": test_lid}
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                print("完整响应:")
                import json
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"错误响应: {response.text}")
                
        except Exception as e:
            print(f"异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_single_lid())
