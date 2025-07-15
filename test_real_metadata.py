#!/usr/bin/env python3
"""
测试真实的元数据获取功能
"""
import asyncio
import httpx


async def test_real_metadata():
    """测试真实的元数据获取"""
    print("🔍 测试真实元数据获取...")
    print("=" * 50)

    # 测试一个有 DOI 的文献
    test_data = {"doi": "10.1038/nature12373", "title": None, "authors": None}

    print(f"测试数据: {test_data}")

    # 提交任务
    async with httpx.AsyncClient() as client:
        print("\n1️⃣ 提交处理请求...")
        response = await client.post(
            "http://localhost:8000/api/literature", json=test_data, timeout=30
        )

        print(f"   状态码: {response.status_code}")

        if response.status_code == 202:
            result = response.json()
            task_id = result.get("taskId")
            print(f"   ✅ 任务ID: {task_id}")

            # 监控任务
            print("\n2️⃣ 监控任务进度...")
            for i in range(30):  # 最多等待30次
                await asyncio.sleep(2)

                status_response = await client.get(
                    f"http://localhost:8000/api/task/{task_id}", timeout=10
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    stage = status_data.get("stage")
                    progress = status_data.get("progress_percentage")

                    print(f"   📊 状态: {status} | 阶段: {stage} | 进度: {progress}%")

                    if status == "success":
                        literature_id = status_data.get("literature_id")
                        print(f"   🎉 任务成功完成！文献ID: {literature_id}")
                        return True
                    elif status == "failure":
                        error = status_data.get("error_info")
                        print(f"   ❌ 任务失败: {error}")
                        return False
                else:
                    print(f"   ❌ 状态查询失败: {status_response.status_code}")
                    return False

            print("   ⏰ 任务超时")
            return False
        else:
            print(f"   ❌ 请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False


if __name__ == "__main__":
    result = asyncio.run(test_real_metadata())
    print(f"\n测试结果: {'✅ 成功' if result else '❌ 失败'}")
