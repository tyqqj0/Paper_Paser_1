#!/usr/bin/env python3
"""
最终验证：端到端功能测试
"""
import requests
import json
import time


def run_test(url, source_type="arxiv"):
    """运行完整的测试流程"""
    print(f"🚀 开始测试: {url}")

    # 提交任务
    payload = {"source": {"url": url, "source_type": source_type}}
    response = requests.post(
        "http://localhost:8000/api/literature", json=payload, timeout=10
    )

    task_or_literature_id = None
    if response.status_code == 202:
        task_or_literature_id = response.json().get("task_id")
    elif response.status_code == 200:
        task_or_literature_id = response.json().get("literature_id")

    if not task_or_literature_id:
        print("❌ 任务提交或查询失败")
        return False

    print(f"✅ 任务或文献ID: {task_or_literature_id}")

    # 等待任务完成
    literature_id = task_or_literature_id
    if len(task_or_literature_id) > 24:  # Task ID is UUID
        print("⏳ 等待任务完成...")
        for _ in range(30):
            status_response = requests.get(
                f"http://localhost:8000/api/task/{task_or_literature_id}", timeout=5
            )
            status = status_response.json()
            if status.get("status") == "success":
                literature_id = status.get("literature_id")
                break
            time.sleep(2)

    if not literature_id or len(literature_id) < 24:
        print("❌ 任务未在预期时间内完成或获取文献ID失败")
        return False

    print(f"✅ 任务完成，文献ID: {literature_id}")

    # 获取并分析结果
    details = requests.get(
        f"http://localhost:8000/api/literature/{literature_id}", timeout=10
    ).json()
    fulltext = requests.get(
        f"http://localhost:8000/api/literature/{literature_id}/fulltext", timeout=10
    ).json()

    references = details.get("references", [])
    parsed_fulltext = fulltext.get("parsed_fulltext")

    print("\n📊 解析结果:")
    print(f"  - 标题: {'成功' if details.get('metadata', {}).get('title') else '失败'}")
    print(
        f"  - 作者: {'成功' if details.get('metadata', {}).get('authors') else '失败'}"
    )
    print(
        f"  - 摘要: {'成功' if details.get('metadata', {}).get('abstract') else '失败'}"
    )
    print(f"  - 参考文献: {len(references)}条 {'成功' if references else '失败'}")
    print(f"  - 全文: {'存在' if parsed_fulltext else '不存在'}")

    return len(references) > 0 and parsed_fulltext is not None


def main():
    print("=== 最终功能验证 ===")

    # 测试 Attention Is All You Need
    success = run_test("https://arxiv.org/abs/1706.03762")

    if success:
        print("\n✅ 所有功能验证成功！")
    else:
        print("\n❌ 功能验证失败！")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    main()
