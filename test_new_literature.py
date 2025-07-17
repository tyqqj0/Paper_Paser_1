 #!/usr/bin/env python3
"""测试新的文献解析"""

import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000/api"

async def test_new_literature():
    """测试新的文献解析"""
    print("=== 测试新的文献解析 ===")
    
    # 使用一个不同的论文
    test_url = "http://arxiv.org/abs/2205.14217"  # 一个不同的ArXiv论文
    print(f"提交文献解析任务: {test_url}")
    
    async with httpx.AsyncClient(timeout=300) as client:
        try:
            # 1. 提交任务
            response = await client.post(
                f"{BASE_URL}/literature",
                json={"source": {"url": test_url}}
            )
            print(f"响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "exists":
                    print(f"文献已存在，ID: {result.get('literatureId')}")
                    # 直接检查这个文献的references
                    lit_response = await client.get(f"{BASE_URL}/literature/{result.get('literatureId')}")
                    if lit_response.status_code == 200:
                        lit_data = lit_response.json()
                        refs = lit_data.get('references', [])
                        print(f"已存在文献的References数量: {len(refs)}")
                        if refs:
                            print("References来源:")
                            sources = {}
                            for ref in refs:
                                source = ref.get('source', 'Unknown')
                                sources[source] = sources.get(source, 0) + 1
                            for source, count in sources.items():
                                print(f"  {source}: {count} 个")
                        else:
                            print("❌ 已存在文献也没有references数据")
                    return
                    
            elif response.status_code == 202:
                task_data = response.json()
                task_id = task_data["taskId"]
                print(f"任务ID: {task_id}")
                
                # 2. 监控任务进度
                print("\n监控任务进度...")
                max_wait = 300  # 5分钟超时
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    try:
                        status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"任务状态: {status_data.get('status')}")
                            print(f"当前阶段: {status_data.get('stage', 'N/A')}")
                            
                            # 检查是否完成
                            if status_data.get("status") == "success":
                                literature_id = status_data.get("literature_id")
                                if literature_id:
                                    print(f"\n✅ 任务完成! 文献ID: {literature_id}")
                                    
                                    # 3. 获取文献详情
                                    lit_response = await client.get(f"{BASE_URL}/literature/{literature_id}")
                                    if lit_response.status_code == 200:
                                        lit_data = lit_response.json()
                                        print(f"\n=== 文献详情 ===")
                                        print(f"标题: {lit_data.get('metadata', {}).get('title', 'N/A')}")
                                        
                                        refs = lit_data.get('references', [])
                                        print(f"References数量: {len(refs)}")
                                        
                                        if refs:
                                            print("\nReferences详情:")
                                            for i, ref in enumerate(refs[:3], 1):  # 显示前3个
                                                raw_text = ref.get('raw_text', 'N/A')
                                                if len(raw_text) > 80:
                                                    raw_text = raw_text[:80] + '...'
                                                print(f"  {i}. Raw: {raw_text}")
                                                print(f"     Source: {ref.get('source', 'N/A')}")
                                                print(f"     Parsed: {bool(ref.get('parsed'))}")
                                                if ref.get('parsed'):
                                                    parsed = ref.get('parsed')
                                                    print(f"     -> Title: {parsed.get('title', 'N/A')}")
                                                    print(f"     -> Year: {parsed.get('year', 'N/A')}")
                                                print()
                                            
                                            # 分析references来源
                                            sources = {}
                                            for ref in refs:
                                                source = ref.get('source', 'Unknown')
                                                sources[source] = sources.get(source, 0) + 1
                                            
                                            print(f"References来源统计:")
                                            for source, count in sources.items():
                                                print(f"  {source}: {count} 个")
                                                
                                        else:
                                            print("❌ 没有找到references数据")
                                    break
                            elif status_data.get("status") == "failure":
                                print(f"❌ 任务失败: {status_data.get('error_message', 'Unknown error')}")
                                break
                                
                    except Exception as e:
                        print(f"检查状态时出错: {e}")
                    
                    await asyncio.sleep(5)  # 等待5秒后再检查
                else:
                    print("❌ 任务超时")
            else:
                print(f"提交失败: {response.text}")
                
        except Exception as e:
            print(f"请求失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_new_literature())