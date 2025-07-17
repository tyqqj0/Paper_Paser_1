#!/usr/bin/env python3
"""通过API检查references数据"""

import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000/api"

async def test_api_references():
    """通过API检查references数据"""
    print("=== 通过API检查References数据 ===")
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            # 先检查现有的文献ID
            known_ids = [
                "6877a57f80b8945ed44473a4",  # 之前的Attention论文
            ]
            
            for lit_id in known_ids:
                print(f"\n--- 检查文献 {lit_id} ---")
                try:
                    response = await client.get(f"{BASE_URL}/literature/{lit_id}")
                    if response.status_code == 200:
                        data = response.json()
                        
                        # 基本信息
                        metadata = data.get('metadata', {})
                        print(f"标题: {metadata.get('title', 'N/A')}")
                        print(f"年份: {metadata.get('year', 'N/A')}")
                        
                        # References信息
                        refs = data.get('references', [])
                        print(f"References数量: {len(refs)}")
                        
                        if refs:
                            print("References详情:")
                            for i, ref in enumerate(refs[:3], 1):
                                print(f"  {i}. Source: {ref.get('source', 'N/A')}")
                                print(f"     Raw: {ref.get('raw_text', 'N/A')[:80]}...")
                                print(f"     Parsed: {bool(ref.get('parsed'))}")
                                if ref.get('parsed'):
                                    parsed = ref.get('parsed')
                                    print(f"     -> Title: {parsed.get('title', 'N/A')}")
                                    print(f"     -> Year: {parsed.get('year', 'N/A')}")
                                print()
                        else:
                            print("❌ 没有references数据")
                            
                    else:
                        print(f"API请求失败: {response.status_code}")
                        
                except Exception as e:
                    print(f"检查文献 {lit_id} 时出错: {e}")
            
            # 测试一个新的文献解析
            print(f"\n=== 测试新的文献解析 ===")
            test_url = "http://arxiv.org/abs/1706.03762"  # 重新测试Attention论文
            print(f"测试URL: {test_url}")
            
            response = await client.post(
                f"{BASE_URL}/literature",
                json={"source": {"url": test_url}}
            )
            
            print(f"响应状态: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"响应: {result}")
                
                if result.get("status") == "exists":
                    lit_id = result.get("literatureId")
                    print(f"文献已存在，ID: {lit_id}")
                    
                    # 检查这个文献的references
                    lit_response = await client.get(f"{BASE_URL}/literature/{lit_id}")
                    if lit_response.status_code == 200:
                        lit_data = lit_response.json()
                        refs = lit_data.get('references', [])
                        print(f"References数量: {len(refs)}")
                        
                        if refs:
                            print("References来源统计:")
                            sources = {}
                            for ref in refs:
                                source = ref.get('source', 'Unknown')
                                sources[source] = sources.get(source, 0) + 1
                            
                            for source, count in sources.items():
                                print(f"  {source}: {count} 个")
                                
                            # 检查解析质量
                            parsed_count = sum(1 for ref in refs if ref.get('parsed'))
                            print(f"解析率: {parsed_count}/{len(refs)} ({parsed_count/len(refs)*100:.1f}%)")
                        else:
                            print("❌ 该文献没有references数据")
                            
            elif response.status_code == 202:
                task_data = response.json()
                task_id = task_data["taskId"]
                print(f"新任务创建: {task_id}")
                
                # 简单等待任务完成
                import time
                for i in range(30):  # 最多等待5分钟
                    await asyncio.sleep(10)
                    
                    status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        print(f"任务状态: {status_data.get('status')} - {status_data.get('stage', 'N/A')}")
                        
                        if status_data.get("status") == "success":
                            lit_id = status_data.get("literature_id")
                            if lit_id:
                                print(f"任务完成，文献ID: {lit_id}")
                                
                                # 检查references
                                lit_response = await client.get(f"{BASE_URL}/literature/{lit_id}")
                                if lit_response.status_code == 200:
                                    lit_data = lit_response.json()
                                    refs = lit_data.get('references', [])
                                    print(f"新文献References数量: {len(refs)}")
                                    
                                    if refs:
                                        print("新文献References示例:")
                                        for i, ref in enumerate(refs[:2], 1):
                                            print(f"  {i}. Source: {ref.get('source', 'N/A')}")
                                            print(f"     Parsed: {bool(ref.get('parsed'))}")
                                            if ref.get('parsed'):
                                                parsed = ref.get('parsed')
                                                print(f"     Title: {parsed.get('title', 'N/A')}")
                                break
                        elif status_data.get("status") == "failure":
                            print(f"任务失败: {status_data.get('error_info', 'Unknown')}")
                            break
                else:
                    print("任务等待超时")
                    
        except Exception as e:
            print(f"API测试失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_api_references()) 