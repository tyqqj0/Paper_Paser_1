#!/usr/bin/env python3
"""
通过API测试元数据解析后的自动查重功能 - 改进版

使用一个可靠的DOI进行测试
"""

import asyncio
import aiohttp
import json
import time

async def test_api_deduplication_v2():
    print("=" * 80)
    print("通过API测试元数据解析后的自动查重功能 - 改进版")
    print("=" * 80)
    
    # 使用一个更可靠的DOI（Attention Is All You Need）
    test_doi = "10.48550/arXiv.1706.03762"
    base_url = "http://localhost:8000"
    
    print(f"🧪 测试DOI: {test_doi}")
    print(f"🌐 API地址: {base_url}")
    
    async with aiohttp.ClientSession() as session:
        # 第一次提交
        print("\n📋 第一次提交文献...")
        
        first_request = {
            "doi": test_doi
        }
        
        async with session.post(
            f"{base_url}/api/resolve",
            json=first_request,
            headers={"Content-Type": "application/json"}
        ) as response:
            if response.status == 202:
                result_1 = await response.json()
                task_id_1 = result_1["task_id"]
                print(f"✅ 第一个任务已提交: {task_id_1}")
            elif response.status == 200:
                result_1 = await response.json()
                print(f"ℹ️  文献已存在: {result_1}")
                print("由于文献已存在，无法测试重复检测逻辑")
                return
            else:
                print(f"❌ 第一次提交失败: {response.status}")
                error_detail = await response.text()
                print(f"错误详情: {error_detail}")
                return
        
        # 等待一段时间让元数据处理完成
        print("⏳ 等待元数据处理...")
        await asyncio.sleep(20)  # 等待20秒，让第一个任务有时间处理元数据
        
        # 检查第一个任务状态
        print(f"\n🔍 检查第一个任务状态...")
        async with session.get(f"{base_url}/api/tasks/{task_id_1}") as response:
            if response.status == 200:
                task_status = await response.json()
                print(f"📊 第一个任务状态: {task_status.get('status')}")
                print(f"📊 当前阶段: {task_status.get('current_stage')}")
                print(f"📊 进度: {task_status.get('overall_progress', 0)}%")
                
                if task_status.get("status") == "failed":
                    print("❌ 第一个任务失败，无法测试重复检测")
                    error_info = task_status.get("error_info", {})
                    print(f"错误信息: {error_info.get('error_message', 'Unknown error')}")
                    return
            else:
                print(f"❌ 无法获取任务状态: {response.status}")
                return
        
        # 第二次提交相同的文献
        print(f"\n📋 第二次提交相同文献（DOI: {test_doi}）...")
        
        second_request = {
            "doi": test_doi
        }
        
        async with session.post(
            f"{base_url}/api/resolve",
            json=second_request,
            headers={"Content-Type": "application/json"}
        ) as response:
            status_2 = response.status
            result_2 = await response.json()
            
            print(f"📊 第二次提交结果 (状态码: {status_2}):")
            print(json.dumps(result_2, indent=2, ensure_ascii=False))
            
            if status_2 == 200:
                print("✅ 成功！第二次提交返回了已存在的文献")
                print(f"🔗 返回的LID: {result_2.get('lid')}")
                print("这说明别名系统工作正常，或者我们的查重修复生效了")
            elif status_2 == 202:
                print("⚠️  第二次提交仍然创建了新任务")
                task_id_2 = result_2["task_id"]
                print(f"新任务ID: {task_id_2}")
                
                # 等待第二个任务完成，看看它如何处理重复
                print("⏳ 等待第二个任务完成...")
                await asyncio.sleep(30)
                
                async with session.get(f"{base_url}/api/tasks/{task_id_2}") as resp:
                    if resp.status == 200:
                        task2_status = await resp.json()
                        print(f"📊 第二个任务最终状态:")
                        print(json.dumps({
                            "status": task2_status.get("status"),
                            "result_type": task2_status.get("result_type"),
                            "literature_id": task2_status.get("literature_id"),
                            "current_stage": task2_status.get("current_stage")
                        }, indent=2, ensure_ascii=False))
                        
                        if task2_status.get("result_type") == "duplicate":
                            print("✅ 第二个任务被正确识别为重复！")
                            print("我们的元数据解析后查重修复生效了")
                        elif task2_status.get("result_type") == "created":
                            print("❌ 第二个任务创建了新文献，查重未生效")
                        else:
                            print(f"❓ 第二个任务结果类型: {task2_status.get('result_type')}")
            else:
                print(f"❓ 未知状态: {status_2}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_deduplication_v2())
