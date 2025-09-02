#!/usr/bin/env python3
"""
通过API测试元数据解析后的自动查重功能

验证场景：
1. 通过API提交一个文献进行处理
2. 在处理过程中，再次提交相同的文献
3. 验证第二次提交能够正确检测重复并返回已有文献
"""

import asyncio
import aiohttp
import json
import time

async def test_api_deduplication():
    print("=" * 80)
    print("通过API测试元数据解析后的自动查重功能")
    print("=" * 80)
    
    # 测试用的DOI
    test_doi = "10.1145/3485447.3512256"
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
                return  # 如果已存在，不继续测试
            else:
                print(f"❌ 第一次提交失败: {response.status}")
                return
        
        # 等待一段时间让元数据处理开始
        print("⏳ 等待元数据处理开始...")
        await asyncio.sleep(10)
        
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
            elif status_2 == 202:
                print("❌ 可能失败！第二次提交仍然创建了新任务")
                print("这可能意味着重复检测没有正常工作")
                task_id_2 = result_2["task_id"]
                print(f"⚠️  新任务ID: {task_id_2}")
            else:
                print(f"❓ 未知状态: {status_2}")
        
        # 检查第一个任务的状态
        print(f"\n🔍 检查第一个任务状态...")
        async with session.get(f"{base_url}/api/tasks/{task_id_1}") as response:
            if response.status == 200:
                task_status = await response.json()
                print(f"📊 第一个任务状态:")
                print(json.dumps({
                    "status": task_status.get("status"),
                    "progress": task_status.get("progress"),
                    "current_stage": task_status.get("current_stage"),
                    "result": task_status.get("result", {}).get("result_type") if task_status.get("result") else None
                }, indent=2, ensure_ascii=False))
            else:
                print(f"❌ 无法获取任务状态: {response.status}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_api_deduplication())
