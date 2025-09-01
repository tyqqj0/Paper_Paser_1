#!/usr/bin/env python3
"""
测试简单的ArXiv论文解析并检查是否保存到数据库
"""

import asyncio
import httpx
import json

async def test_simple_arxiv():
    """测试ArXiv论文解析"""
    print("📚 测试ArXiv论文解析 - 验证数据库保存")
    print("=" * 50)
    
    base_url = "http://localhost:8000/api"
    
    # 使用一个简单的ArXiv论文
    arxiv_url = "https://arxiv.org/abs/1706.03762"  # Transformer论文
    
    async with httpx.AsyncClient() as client:
        print(f"🔍 解析论文: {arxiv_url}")
        
        # 创建任务
        response = await client.post(
            f"{base_url}/resolve/",
            json={"url": arxiv_url}
        )
        
        if response.status_code != 200:
            print(f"❌ 任务创建失败: {response.status_code}")
            return None
            
        task_data = response.json()
        task_id = task_data["task_id"]
        print(f"✅ 任务创建: {task_id}")
        
        # 使用SSE监听任务状态
        literature_id = None
        final_status = None
        
        async with client.stream(
            "GET",
            f"{base_url}/tasks/{task_id}/stream",
            headers={"Accept": "text/event-stream"}
        ) as stream:
            print("📡 监听解析进度...")
            
            async for line in stream.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        try:
                            parsed_data = json.loads(data)
                            status = parsed_data.get("status")
                            stage = parsed_data.get("stage", "")
                            
                            print(f"   {status}: {stage}")
                            
                            if status == "completed":
                                final_status = "completed"
                                # 尝试获取literature_id
                                literature_id = parsed_data.get("literature_id")
                                print(f"   ✅ 解析完成! Literature ID: {literature_id}")
                                break
                            elif status == "failed":
                                final_status = "failed"
                                error = parsed_data.get("error", {})
                                print(f"   ❌ 解析失败: {error}")
                                break
                                
                        except:
                            pass
        
        # 检查结果
        if final_status == "completed" and literature_id:
            print(f"\n🎉 成功！Literature ID: {literature_id}")
            
            # 测试关系图API，看看这个LID是否存在
            print(f"🔍 验证LID是否存在于数据库...")
            response = await client.get(
                f"{base_url}/graphs",
                params={"lids": literature_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                nodes = data.get("nodes", [])
                
                if nodes:
                    print(f"   ✅ 验证成功! 在数据库中找到 {len(nodes)} 个节点")
                    for node in nodes:
                        print(f"     - {node.get('lid')}: {node.get('title', 'No title')[:50]}...")
                    return literature_id
                else:
                    print(f"   ⚠️ 关系图API没有找到节点，但解析报告成功")
            else:
                print(f"   ❌ 关系图API错误: {response.status_code}")
                
        elif final_status == "completed":
            print(f"   ⚠️ 解析完成但没有返回Literature ID")
        else:
            print(f"   ❌ 解析未成功完成")
        
        return None

if __name__ == "__main__":
    result = asyncio.run(test_simple_arxiv())
    if result:
        print(f"\n🚀 可以使用这个LID测试关系图API: {result}")
    else:
        print(f"\n💡 需要进一步调试数据管道的保存逻辑")
