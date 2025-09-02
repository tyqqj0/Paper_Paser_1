#!/usr/bin/env python3
"""
测试任务结果类型判断修复
验证基于组件状态而不是标题检查的逻辑
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the backend path to sys.path
backend_path = Path(__file__).parent / "literature_parser_backend"
sys.path.insert(0, str(backend_path))

from db.dao import LiteratureDAO
from models.literature import TaskInfoModel
from worker.tasks import TaskResultType


async def test_task_result_logic():
    """测试任务结果判断逻辑"""
    
    print("🧪 测试任务结果类型判断修复")
    print("=" * 50)
    
    # 模拟不同的组件状态
    test_cases = [
        {
            "name": "元数据和引文都成功",
            "component_status": {
                "metadata": {"status": "success"},
                "references": {"status": "success"},
                "content": {"status": "failed"}  # 内容失败不影响
            },
            "expected_overall": "completed",
            "expected_result": TaskResultType.CREATED
        },
        {
            "name": "元数据成功，引文失败",
            "component_status": {
                "metadata": {"status": "success"},
                "references": {"status": "failed"},
                "content": {"status": "success"}
            },
            "expected_overall": "partial_completed",
            "expected_result": TaskResultType.CREATED  # 部分成功也算创建成功
        },
        {
            "name": "元数据失败，引文成功", 
            "component_status": {
                "metadata": {"status": "failed"},
                "references": {"status": "success"},
                "content": {"status": "success"}
            },
            "expected_overall": "failed",
            "expected_result": TaskResultType.PARSING_FAILED
        },
        {
            "name": "元数据部分成功，引文成功",
            "component_status": {
                "metadata": {"status": "partial"},
                "references": {"status": "success"},
                "content": {"status": "failed"}
            },
            "expected_overall": "completed",
            "expected_result": TaskResultType.CREATED
        },
        {
            "name": "所有组件都失败",
            "component_status": {
                "metadata": {"status": "failed"},
                "references": {"status": "failed"},
                "content": {"status": "failed"}
            },
            "expected_overall": "failed",
            "expected_result": TaskResultType.PARSING_FAILED
        }
    ]
    
    # 创建DAO实例来测试状态计算
    dao = LiteratureDAO()
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n📋 测试案例 {i}: {case['name']}")
        
        # 测试状态计算
        actual_overall = dao._calculate_overall_status(case['component_status'])
        
        # 模拟任务结果类型判断逻辑
        if actual_overall == "completed":
            actual_result = TaskResultType.CREATED
        elif actual_overall in ["partial_completed", "processing"]:
            actual_result = TaskResultType.CREATED
        else:  # failed
            actual_result = TaskResultType.PARSING_FAILED
        
        # 检查结果
        overall_correct = actual_overall == case['expected_overall']
        result_correct = actual_result == case['expected_result']
        
        print(f"   组件状态: {case['component_status']}")
        print(f"   预期整体状态: {case['expected_overall']}")
        print(f"   实际整体状态: {actual_overall} {'✅' if overall_correct else '❌'}")
        print(f"   预期任务结果: {case['expected_result']}")
        print(f"   实际任务结果: {actual_result} {'✅' if result_correct else '❌'}")
        
        if overall_correct and result_correct:
            print(f"   ✅ 测试通过")
        else:
            print(f"   ❌ 测试失败")
            return False
    
    print(f"\n🎉 所有测试用例通过！")
    print("\n📝 修复总结:")
    print("- 任务结果类型现在基于实际组件状态判断")
    print("- 元数据+引文成功 → CREATED (成功)")  
    print("- 元数据成功但引文失败 → CREATED (部分成功)")
    print("- 元数据失败 → PARSING_FAILED (失败)")
    print("- 不再依赖标题中的错误指示符")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_task_result_logic())
    sys.exit(0 if success else 1)


