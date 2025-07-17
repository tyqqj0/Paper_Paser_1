#!/usr/bin/env python3
"""简单的references测试"""

import asyncio
import httpx
import time
import json

BASE_URL = "http://127.0.0.1:8000/api"

async def test_references():
    """测试references解析"""
    print("=== 测试References解析 ===")
    
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. 提交一个新的文献解析任务
        test_url = "http://arxiv.org/abs/1706.03762"  # Attention is All You Need
        print(f"提交文献解析任务: {test_url}")
        
        try:
            response = await client.post(
                f"{BASE_URL}/literature",
                json={"source": {"url": test_url}}
            )
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code != 202:
                print(f"提交失败: {response.text}")
                return
                
            task_data = response.json()
            task_id = task_data["taskId"]
            print(f"任务ID: {task_id}")
            
            # 2. 轮询任务状态
            print("\n监控任务进度...")
            max_wait = 300  # 5分钟超时
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                try:
                    status_response = await client.get(f"{BASE_URL}/tasks/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"任务状态: {status_data}")
                        
                        # 检查是否完成
                        if status_data.get("status") == "success":
                            literature_id = status_data.get("literature_id")
                            if literature_id:
                                print(f"\n✅ 任务完成! 文献ID: {literature_id}")
                                
                                # 3. 获取文献详情，检查references
                                lit_response = await client.get(f"{BASE_URL}/literature/{literature_id}")
                                if lit_response.status_code == 200:
                                    lit_data = lit_response.json()
                                    print(f"\n=== 文献详情 ===")
                                    print(f"标题: {lit_data.get('metadata', {}).get('title', 'N/A')}")
                                    
                                    refs = lit_data.get('references', [])
                                    print(f"References数量: {len(refs)}")
                                    
                                    if refs:
                                        print("\nReferences详情:")
                                        for i, ref in enumerate(refs[:5], 1):  # 显示前5个
                                            raw_text = ref.get('raw_text', 'N/A')
                                            if len(raw_text) > 100:
                                                raw_text = raw_text[:100] + '...'
                                            print(f"  {i}. Raw: {raw_text}")
                                            print(f"     Source: {ref.get('source', 'N/A')}")
                                            print(f"     Parsed: {bool(ref.get('parsed'))}")
                                            if ref.get('parsed'):
                                                parsed = ref.get('parsed')
                                                print(f"     -> Title: {parsed.get('title', 'N/A')}")
                                                print(f"     -> Year: {parsed.get('year', 'N/A')}")
                                            print()
                                        
                                        if len(refs) > 5:
                                            print(f"  ... 还有 {len(refs) - 5} 个references")
                                    else:
                                        print("❌ 没有找到references数据")
                                else:
                                    print(f"获取文献详情失败: {lit_response.status_code}")
                                break
                        elif status_data.get("status") == "failure":
                            print(f"❌ 任务失败: {status_data.get('error_message', 'Unknown error')}")
                            break
                            
                except Exception as e:
                    print(f"检查状态时出错: {e}")
                
                await asyncio.sleep(5)  # 等待5秒后再检查
            else:
                print("❌ 任务超时")
                
        except Exception as e:
            print(f"请求失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_references()) 