#!/usr/bin/env python3
"""
简化的系统测试脚本
"""

import asyncio
import time
import os
import httpx

# Give services a moment to start up
# time.sleep(5) # No need to sleep when running inside the same network

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8088/api/v1")
DOI = "10.1109/5.771073"
ARXIV_ID = "1706.03762"


async def test_literature_parser():
    """测试文献解析器系统"""
    print("🚀 Literature Parser 系统测试")
    print("=" * 50)

    # 使用一个新的测试URL
    test_url = "http://arxiv.org/abs/2205.14217"  # 已知存在的ArXiv论文

    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. API健康检查
        print("\n1️⃣ API健康检查...")
        try:
            response = await client.get("http://127.0.0.1:8088/api/health")
            if response.status_code == 200:
                print("   ✅ API服务正常")
            else:
                print(f"   ❌ API服务异常: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            print(f"   ❌ API连接失败: {e}")
            return False

        # 2. 提交文献处理任务
        print(f"\n2️⃣ 提交文献处理任务...")
        try:
            payload = {"url": test_url}
            response = await client.post(
                "http://127.0.0.1:8088/api/literature", json=payload
            )

            print(f"   ✅ 任务提交成功")
            print(f"   📋 响应: {response.text}")

            response_data = response.json()
            if "taskId" not in response_data:
                print("   ❌ 没有返回任务ID")
                return False

            task_id = response_data["taskId"]
            print(f"   🆔 任务ID: {task_id}")

        except Exception as e:
            print(f"   ❌ 任务提交失败: {e}")
            return False

        # 3. 监控任务进度
        print(f"\n3️⃣ 监控任务进度 (ID: {task_id})...")
        max_wait_time = 120  # 最多等待2分钟
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = await client.get(f"http://127.0.0.1:8088/api/task/{task_id}")
                task_data = response.json()

                status = task_data.get("status", "unknown")
                stage = task_data.get("current_stage", "unknown")
                progress = task_data.get("progress", 0)

                print(f"   📊 状态: {status} | 阶段: {stage} | 进度: {progress}%")

                if status == "success":
                    literature_id = (
                        task_data.get("result", {}).get("literature_id")
                        or task_data.get("literature_id")
                        or task_data.get("result")
                    )
                    if literature_id:
                        print(f"   🎉 任务完成！文献ID: {literature_id}")
                        break
                    else:
                        print("   ❌ 任务完成但没有返回文献ID")
                        print(f"   📋 完整响应: {task_data}")
                        return False
                elif status == "failure":
                    error_msg = task_data.get("result", {}).get("error", "未知错误")
                    print(f"   ❌ 任务失败: {error_msg}")
                    return False

                await asyncio.sleep(3)

            except Exception as e:
                print(f"   ❌ 任务状态查询失败: {e}")
                await asyncio.sleep(3)
                continue
        else:
            print(f"   ⏰ 任务超时 (>{max_wait_time}秒)")
            return False

        # 4. 检查文献信息
        print(f"\n4️⃣ 检查文献信息 (ID: {literature_id})...")
        try:
            response = await client.get(
                f"http://127.0.0.1:8088/api/literature/{literature_id}"
            )
            if response.status_code == 200:
                print("   ✅ 文献信息获取成功")
                lit_data = response.json()
                print(f"   📰 标题: {lit_data.get('title', 'Unknown')}")
                print(f"   🔗 DOI: {lit_data.get('doi', 'Unknown')}")
                print(f"   📅 年份: {lit_data.get('year', 'Unknown')}")
                print(f"   👥 作者数: {len(lit_data.get('authors', []))}")
                print(f"   📚 参考文献数: {len(lit_data.get('references', []))}")
            else:
                print(f"   ❌ 文献信息获取失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ 文献信息查询失败: {e}")
            return False

        print("\n" + "=" * 50)
        print("🎉 系统测试全部通过！")
        print("✅ Literature Parser 系统运行正常")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_literature_parser())
    if not success:
        print("\n❌ 系统测试失败")
        exit(1)