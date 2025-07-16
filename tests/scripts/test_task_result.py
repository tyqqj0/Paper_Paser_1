#!/usr/bin/env python3
"""
测试任务结果详情
"""

import json
import time

import requests


def test_task_result():
    """测试任务结果详情"""

    # 1. 提交任务
    print("🔍 提交新的测试任务...")

    test_data = {"doi": "10.1038/nature12373", "title": None, "authors": None}

    response = requests.post("http://localhost:8000/api/literature", json=test_data)

    print(f"   状态码: {response.status_code}")
    if response.status_code != 202:
        print(f"   错误: {response.text}")
        return

    result = response.json()
    print(f"   响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 检查不同可能的字段名
    task_id = result.get("task_id") or result.get("id") or result.get("taskId")
    if not task_id:
        print("   ❌ 响应中没有找到任务ID")
        return

    print(f"   ✅ 任务ID: {task_id}")

    # 2. 等待任务完成
    print("\n⏳ 等待任务完成...")
    time.sleep(5)

    # 3. 检查任务状态
    print("\n📊 检查任务状态...")
    response = requests.get(f"http://localhost:8000/api/task/{task_id}")

    if response.status_code == 200:
        task_info = response.json()
        print(f"   完整响应: {json.dumps(task_info, indent=2, ensure_ascii=False)}")

        # 检查特定字段
        if "literature_id" in task_info:
            print(f"   📚 文献ID: {task_info['literature_id']}")
        else:
            print("   ❌ 响应中没有 literature_id 字段")

        if "resource_url" in task_info:
            print(f"   🔗 资源URL: {task_info['resource_url']}")
        else:
            print("   ❌ 响应中没有 resource_url 字段")

    else:
        print(f"   ❌ 获取任务状态失败: {response.status_code}")
        print(f"   错误: {response.text}")

    # 4. 尝试直接从Redis获取结果
    print("\n🔍 尝试检查任务原始结果...")
    try:
        # 使用docker exec在容器内执行redis命令
        import subprocess

        # 检查Redis中的任务结果
        cmd = f'docker exec literature_parser_backend-redis-1 redis-cli GET "celery-task-meta-{task_id}"'
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            print(f"   Redis原始结果: {result.stdout.strip()}")
        else:
            print(f"   无法从Redis获取结果: {result.stderr}")

    except Exception as e:
        print(f"   Redis检查失败: {e}")


if __name__ == "__main__":
    test_task_result()
