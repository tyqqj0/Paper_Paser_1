#!/usr/bin/env python3
"""
简单系统测试 - 验证系统整体功能
"""

import requests
import time
import json


def test_system():
    print("🚀 Literature Parser 系统测试")
    print("=" * 50)

    # 1. 健康检查
    print("\n1️⃣ API健康检查...")
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=10)
        if response.status_code == 200:
            print("   ✅ API服务正常")
        else:
            print(f"   ❌ API异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ API连接失败: {e}")
        return False

    # 2. 提交文献任务
    print("\n2️⃣ 提交文献处理任务...")
    test_data = {"doi": "10.1038/nature12373"}

    try:
        response = requests.post(
            "http://localhost:8000/api/literature", json=test_data, timeout=30
        )

        if response.status_code in [200, 202]:
            result = response.json()
            print(f"   ✅ 任务提交成功")
            print(f"   📋 响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

            # 获取任务ID
            task_id = result.get("taskId") or result.get("task_id")
            if task_id:
                print(f"   🆔 任务ID: {task_id}")
                return task_id
            else:
                print("   ❌ 没有返回任务ID")
                return False
        else:
            print(f"   ❌ 任务提交失败: {response.status_code}")
            print(f"   📄 响应: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ 提交异常: {e}")
        return False


def monitor_task(task_id, max_wait=120):
    """监控任务进度"""
    print(f"\n3️⃣ 监控任务进度 (ID: {task_id})...")

    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"http://localhost:8000/api/task/{task_id}", timeout=10
            )

            if response.status_code == 200:
                task_info = response.json()
                status = task_info.get("status", "unknown")
                stage = task_info.get("current_stage", "unknown")
                progress = task_info.get("progress", 0)

                print(f"   📊 状态: {status} | 阶段: {stage} | 进度: {progress}%")

                if status == "success":
                    literature_id = task_info.get("literature_id")
                    print(f"   🎉 任务完成！文献ID: {literature_id}")
                    return literature_id
                elif status == "failed":
                    error = task_info.get("error", "Unknown error")
                    print(f"   ❌ 任务失败: {error}")
                    return False

                time.sleep(5)
            else:
                print(f"   ⚠️ 查询状态失败: {response.status_code}")
                time.sleep(5)

        except Exception as e:
            print(f"   ⚠️ 查询异常: {e}")
            time.sleep(5)

    print(f"   ⏰ 任务超时 ({max_wait}秒)")
    return False


def check_literature(literature_id):
    """检查文献信息"""
    print(f"\n4️⃣ 检查文献信息 (ID: {literature_id})...")

    try:
        response = requests.get(
            f"http://localhost:8000/api/literature/{literature_id}", timeout=10
        )

        if response.status_code == 200:
            lit_info = response.json()
            print("   ✅ 文献信息获取成功")

            # 显示关键信息
            metadata = lit_info.get("metadata", {})
            identifiers = lit_info.get("identifiers", {})
            references = lit_info.get("references", [])

            print(f"   📰 标题: {metadata.get('title', '未知')}")
            print(f"   🔗 DOI: {identifiers.get('doi', '无')}")
            print(f"   📅 年份: {metadata.get('year', '未知')}")
            print(f"   👥 作者数: {len(metadata.get('authors', []))}")
            print(f"   📚 参考文献数: {len(references)}")

            return True
        else:
            print(f"   ❌ 获取失败: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ 获取异常: {e}")
        return False


def main():
    # 测试系统
    task_id = test_system()
    if not task_id:
        print("\n❌ 系统测试失败")
        return

    # 监控任务
    literature_id = monitor_task(task_id)
    if not literature_id:
        print("\n❌ 任务执行失败")
        return

    # 检查结果
    success = check_literature(literature_id)

    print("\n" + "=" * 50)
    if success:
        print("🎉 系统测试全部通过！")
        print("✅ Literature Parser 系统运行正常")
    else:
        print("❌ 系统测试部分失败")
        print("💡 请检查日志获取更多信息")


if __name__ == "__main__":
    main()
