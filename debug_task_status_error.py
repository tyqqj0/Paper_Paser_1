#!/usr/bin/env python3
"""
调试TaskStatusDTO验证错误的脚本
用于分析和修复created_at/updated_at字段缺失的问题
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

from datetime import datetime
from pydantic import ValidationError
from literature_parser_backend.models.task import TaskStatusDTO, TaskExecutionStatus

def test_task_status_dto_creation():
    """测试TaskStatusDTO的创建，模拟错误情况"""
    
    print("=== 测试TaskStatusDTO创建 ===")
    
    # 模拟从日志中看到的错误情况
    # 错误信息显示缺少created_at和updated_at字段
    response_data_missing_timestamps = {
        'task_id': '93562dee-fe09-408b-8a13-ced15ea4a02d', 
        'status': 'pending'
    }
    
    print(f"1. 测试缺少必需字段的数据: {response_data_missing_timestamps}")
    
    try:
        # 这应该会失败，因为缺少必需字段
        dto = TaskStatusDTO(**response_data_missing_timestamps)
        print("   ✓ 成功创建（意外！）")
    except ValidationError as e:
        print(f"   ✗ 验证错误: {e}")
        for error in e.errors():
            print(f"     - {error['loc'][0]}: {error['msg']}")
    
    print("\n2. 测试包含所有必需字段的数据:")
    
    # 创建包含所有必需字段的数据
    complete_data = {
        'task_id': '93562dee-fe09-408b-8a13-ced15ea4a02d',
        'execution_status': TaskExecutionStatus.PENDING,
        'status': 'pending',
        'overall_progress': 0,
        'current_stage': '任务正在等待'
    }
    
    print(f"   数据: {complete_data}")
    
    try:
        dto = TaskStatusDTO(**complete_data)
        print("   ✓ 成功创建TaskStatusDTO")
        print(f"   task_id: {dto.task_id}")
        print(f"   execution_status: {dto.execution_status}")
        print(f"   status: {dto.status}")
    except ValidationError as e:
        print(f"   ✗ 验证错误: {e}")

def analyze_taskstatus_dto_fields():
    """分析TaskStatusDTO的字段定义"""
    
    print("\n=== 分析TaskStatusDTO字段定义 ===")
    
    from pydantic import BaseModel
    from literature_parser_backend.models.task import TaskStatusDTO
    
    # 获取字段信息
    fields = TaskStatusDTO.model_fields
    
    print("TaskStatusDTO字段:")
    for field_name, field_info in fields.items():
        required = not field_info.is_required() if hasattr(field_info, 'is_required') else 'unknown'
        print(f"  {field_name}: {field_info.annotation} (required: {required})")
    
    # 检查是否有created_at和updated_at字段
    has_created_at = 'created_at' in fields
    has_updated_at = 'updated_at' in fields
    
    print(f"\n检查时间字段:")
    print(f"  has created_at: {has_created_at}")
    print(f"  has updated_at: {has_updated_at}")
    
    if not (has_created_at or has_updated_at):
        print("  ✓ TaskStatusDTO确实没有created_at/updated_at字段")
        print("  这说明错误可能来自其他地方")

def check_task_api_code():
    """检查任务API代码中可能的问题"""
    
    print("\n=== 检查可能的代码问题 ===")
    
    # 这里我们模拟可能导致错误的情况
    # 错误日志显示: return TaskStatusDTO(**response_data)
    # 但是response_data包含了不属于TaskStatusDTO的字段
    
    # 可能的错误场景：某个地方返回了包含created_at/updated_at的数据
    problematic_data = {
        'task_id': '93562dee-fe09-408b-8a13-ced15ea4a02d',
        'status': 'pending',
        'created_at': datetime.now(),  # 这个字段不应该在TaskStatusDTO中
        'updated_at': datetime.now()   # 这个字段也不应该在TaskStatusDTO中
    }
    
    print("模拟错误场景 - 数据包含不应该的字段:")
    print(f"  {list(problematic_data.keys())}")
    
    try:
        # 这可能会失败
        dto = TaskStatusDTO(**problematic_data)
        print("  ✓ 意外成功（可能字段被忽略了）")
    except ValidationError as e:
        print(f"  ✗ 验证错误: {e}")
    except Exception as e:
        print(f"  ✗ 其他错误: {e}")

if __name__ == "__main__":
    test_task_status_dto_creation()
    analyze_taskstatus_dto_fields()
    check_task_api_code()
    
    print("\n=== 总结 ===")
    print("基于错误日志，问题可能是:")
    print("1. 某个地方的代码在使用 TaskStatusDTO(**data) 时")
    print("2. data 中包含了 created_at/updated_at 字段")
    print("3. 但TaskStatusDTO模型没有定义这些字段")
    print("4. 可能是代码版本不一致或有地方错误地传递了LiteratureProcessingStatus的数据")



