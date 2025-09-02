#!/usr/bin/env python3
"""
测试元数据解析后的自动查重功能

验证场景：
1. 提交一个文献进行处理
2. 在元数据解析完成后，再次提交相同的文献
3. 验证第二次提交能够正确检测重复并返回已有文献，而不是创建新节点
"""

import asyncio
import json
import time
from literature_parser_backend.worker.tasks import process_literature_task

async def test_post_metadata_deduplication():
    print("=" * 80)
    print("测试元数据解析后的自动查重功能")
    print("=" * 80)
    
    # 测试用的DOI
    test_doi = "10.1145/3485447.3512256"
    
    print(f"🧪 测试DOI: {test_doi}")
    
    # 第一次提交
    print("\n📋 第一次提交文献...")
    task_data_1 = {
        "identifiers": {"doi": test_doi},
        "title": "First submission"
    }
    
    task_1 = process_literature_task.delay(task_data_1)
    print(f"✅ 第一个任务已提交: {task_1.id}")
    
    # 等待一段时间让元数据处理完成（但不要等到完全完成）
    print("⏳ 等待元数据处理完成...")
    await asyncio.sleep(15)  # 等待15秒，足够元数据处理完成
    
    # 第二次提交相同的文献
    print(f"\n📋 第二次提交相同文献（DOI: {test_doi}）...")
    task_data_2 = {
        "identifiers": {"doi": test_doi},
        "title": "Second submission (should be detected as duplicate)"
    }
    
    task_2 = process_literature_task.delay(task_data_2)
    print(f"✅ 第二个任务已提交: {task_2.id}")
    
    # 等待第二个任务完成
    print("⏳ 等待第二个任务完成...")
    result_2 = task_2.get(timeout=60)
    
    print(f"\n📊 第二个任务结果:")
    print(json.dumps(result_2, indent=2, ensure_ascii=False))
    
    # 验证结果
    if result_2.get("result_type") == "duplicate":
        print("✅ 成功！第二次提交被正确识别为重复")
        print(f"🔗 返回的已有文献ID: {result_2.get('literature_id')}")
    elif result_2.get("result_type") == "created":
        print("❌ 失败！第二次提交被错误地创建为新文献")
        print(f"⚠️  创建的新文献ID: {result_2.get('literature_id')}")
    else:
        print(f"❓ 未知结果类型: {result_2.get('result_type')}")
    
    # 等待第一个任务也完成
    print("\n⏳ 等待第一个任务完成...")
    try:
        result_1 = task_1.get(timeout=120)
        print(f"\n📊 第一个任务结果:")
        print(json.dumps(result_1, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️  第一个任务可能仍在运行或失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_post_metadata_deduplication())
