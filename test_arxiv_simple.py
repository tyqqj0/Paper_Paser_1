#!/usr/bin/env python3
"""
简单测试ArXiv论文解析，验证数据管道修复
"""

import asyncio
import httpx

async def test_arxiv_simple():
    """测试ArXiv论文解析"""
    print("🔍 测试ArXiv论文解析...")
    
    url = "https://arxiv.org/abs/1706.03762"
    
    # 创建任务
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/tasks/literature/",
            json={"url": url}
        )
        
        if response.status_code != 200:
            print(f"❌ 任务创建失败: {response.status_code}")
            return
            
        task_data = response.json()
        task_id = task_data["task_id"]
        print(f"✅ 任务创建成功: {task_id}")
        
        # 使用SSE监听任务状态
        async with client.stream(
            "GET",
            f"http://localhost:8000/api/tasks/{task_id}/stream",
            headers={"Accept": "text/event-stream"}
        ) as stream:
            print("📡 SSE连接已建立...")
            
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        try:
                            import json
                            parsed_data = json.loads(data)
                            status = parsed_data.get("status")
                            
                            if status == "completed":
                                print(f"✅ 任务完成: {parsed_data}")
                                return True
                            elif status == "failed":
                                print(f"❌ 任务失败: {parsed_data}")
                                return False
                            else:
                                print(f"🔄 进度: {status}")
                                
                        except Exception as e:
                            print(f"📝 SSE数据: {data}")

if __name__ == "__main__":
    success = asyncio.run(test_arxiv_simple())
    print(f"测试{'成功' if success else '失败'}")
