#!/usr/bin/env python3
"""快速测试新任务处理"""

import asyncio
import httpx
import time

async def main():
    client = httpx.AsyncClient(timeout=60.0)
    
    try:
        # 1. 提交新任务
        print("🚀 提交新任务...")
        test_data = {
            "title": "Test Paper 2025",
            "authors": ["Test Author"]
        }
        
        response = await client.post(
            "http://localhost:8000/api/literature",
            json=test_data
        )
        
        print(f"状态码: {response.status_code}")
        if response.status_code != 200:
            print(f"响应内容: {response.text}")
            
        result = response.json()
        print(f"响应: {result}")
        
        if result.get("taskId"):
            task_id = result["taskId"]
            print(f"\n⏱️ 等待任务完成: {task_id}")
            
            # 2. 监控任务
            for i in range(10):
                await asyncio.sleep(2)
                task_response = await client.get(f"http://localhost:8000/api/task/{task_id}")
                task_data = task_response.json()
                
                status = task_data.get("status")
                print(f"   第{i+1}次检查: {status}")
                
                if status == "success":
                    print(f"✅ 任务成功！返回数据: {task_data}")
                    break
                elif status == "failure":
                    print(f"❌ 任务失败: {task_data}")
                    break
                    
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
