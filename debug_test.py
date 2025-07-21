#!/usr/bin/env python3
"""
调试测试脚本 - 专门用于调试新功能的问题
"""

import asyncio
import json
import logging
import time
import traceback
from typing import Dict, Any

import httpx

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000/api"


async def debug_test():
    """调试测试"""
    print("🔍 开始调试测试")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. 检查API健康状态
        print("1️⃣ 检查API健康状态...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text}")
        except Exception as e:
            print(f"   错误: {e}")

        # 2. 检查各个服务的健康状态
        print("\n2️⃣ 检查服务状态...")
        endpoints = [
            "/health",
            "/docs",  # API文档
        ]

        for endpoint in endpoints:
            try:
                response = await client.get(f"{BASE_URL}{endpoint}")
                print(f"   {endpoint}: {response.status_code}")
            except Exception as e:
                print(f"   {endpoint}: 错误 - {e}")

        # 3. 提交一个简单的测试任务
        print("\n3️⃣ 提交测试任务...")
        test_payload = {"source": {"url": "https://arxiv.org/abs/1706.03762"}}

        print(f"   请求负载: {json.dumps(test_payload, indent=2)}")

        try:
            response = await client.post(f"{BASE_URL}/literature", json=test_payload)
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text}")

            if response.status_code == 202:
                task_data = response.json()
                task_id = task_data["task_id"]
                print(f"   任务ID: {task_id}")

                # 4. 监控任务状态（详细版）
                print(f"\n4️⃣ 监控任务状态...")
                for i in range(10):  # 只监控10次
                    try:
                        status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                        print(f"\n   第{i+1}次检查:")
                        print(f"   状态码: {status_response.status_code}")

                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            print(f"   任务状态: {status_data.get('status')}")
                            print(
                                f"   总体进度: {status_data.get('overall_progress', 0)}%"
                            )

                            # 显示组件状态
                            component_status = status_data.get("component_status", {})
                            if component_status:
                                print("   组件状态:")
                                for comp, info in component_status.items():
                                    if isinstance(info, dict):
                                        print(
                                            f"     {comp}: {info.get('status')} - {info.get('stage')}"
                                        )
                                        if info.get("error_info"):
                                            print(f"       错误: {info['error_info']}")

                            # 显示详细信息
                            if status_data.get("details"):
                                print(f"   详细信息: {status_data['details']}")
                        else:
                            print(f"   响应错误: {status_response.text}")

                        if status_data.get("status") in ["success", "failed"]:
                            break

                        await asyncio.sleep(5)

                    except Exception as e:
                        print(f"   监控错误: {e}")
                        await asyncio.sleep(2)

        except Exception as e:
            print(f"   提交错误: {e}")
            traceback.print_exc()

        # 5. 检查后端日志（如果可能）
        print("\n5️⃣ 建议检查:")
        print("   - Docker容器日志: docker-compose logs api")
        print("   - Worker日志: docker-compose logs worker")
        print("   - Redis连接: docker-compose logs redis")
        print("   - MongoDB连接: docker-compose logs db")


if __name__ == "__main__":
    asyncio.run(debug_test())
