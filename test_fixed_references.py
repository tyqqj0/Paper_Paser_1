#!/usr/bin/env python3
"""测试修复后的references功能"""

import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000/api"

async def test_fixed_references():
    """测试修复后的references功能"""
    print("=== 测试修复后的References功能 ===")
    
    # 使用一个新的论文URL
    test_url = "http://arxiv.org/abs/2010.11929"  # GPT-3论文
    print(f"提交新的文献解析任务: {test_url}")
    
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
                    # 检查已存在文献的references
                    await check_literature_references(client, result.get('literatureId'))
                    return
                    
            elif response.status_code == 202:
                task_data = response.json()
                task_id = task_data["taskId"]
                print(f"任务ID: {task_id}")
                
                # 2. 监控任务进度
                print("\n监控任务进度...")
                max_wait = 180  # 3分钟超时
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    try:
                        status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"任务状态: {status_data.get('status')}")
                            print(f"当前阶段: {status_data.get('stage', 'N/A')}")
                            
                            # 检查组件状态（如果有的话）
                            if "component_status" in status_data:
                                comp_status = status_data["component_status"]
                                print("组件状态:")
                                for component, status in comp_status.items():
                                    print(f"  {component}: {status.get('status')} - {status.get('stage', 'N/A')}")
                            
                            # 检查是否完成
                            if status_data.get("status") == "success":
                                literature_id = status_data.get("literature_id")
                                if literature_id:
                                    print(f"\n✅ 任务完成! 文献ID: {literature_id}")
                                    await check_literature_references(client, literature_id)
                                break
                            elif status_data.get("status") == "failure":
                                print(f"❌ 任务失败: {status_data.get('error_info', 'Unknown error')}")
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

async def check_literature_references(client, literature_id):
    """检查文献的references"""
    print(f"\n=== 检查文献 {literature_id} 的References ===")
    
    try:
        lit_response = await client.get(f"{BASE_URL}/literature/{literature_id}")
        if lit_response.status_code == 200:
            lit_data = lit_response.json()
            print(f"标题: {lit_data.get('metadata', {}).get('title', 'N/A')}")
            
            refs = lit_data.get('references', [])
            print(f"References数量: {len(refs)}")
            
            if refs:
                print("\nReferences详情:")
                for i, ref in enumerate(refs[:3], 1):  # 显示前3个
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
                        print(f"     -> Authors: {len(parsed.get('authors', []))} 位作者")
                    print()
                
                if len(refs) > 3:
                    print(f"  ... 还有 {len(refs) - 3} 个references")
                
                # 分析references来源
                sources = {}
                for ref in refs:
                    source = ref.get('source', 'Unknown')
                    sources[source] = sources.get(source, 0) + 1
                
                print(f"\nReferences来源统计:")
                for source, count in sources.items():
                    print(f"  {source}: {count} 个")
                    
                # 检查parsed比例
                parsed_count = sum(1 for ref in refs if ref.get('parsed'))
                print(f"\n解析统计:")
                print(f"已解析: {parsed_count}/{len(refs)} ({parsed_count/len(refs)*100:.1f}%)")
                
            else:
                print("❌ 没有找到references数据")
        else:
            print(f"获取文献详情失败: {lit_response.status_code}")
            
    except Exception as e:
        print(f"检查references时出错: {e}")

if __name__ == '__main__':
    asyncio.run(test_fixed_references()) 