#!/usr/bin/env python3
"""
分析文献解析失败的原因
基于测试报告和错误日志，找出"Unknown error"的根本原因
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'literature_parser_backend'))

import json
from datetime import datetime
from pathlib import Path

def analyze_test_reports():
    """分析测试报告中的失败模式"""
    
    print("=== 分析测试报告中的失败模式 ===")
    
    # 找到所有测试报告
    test_files = list(Path('.').glob('test_report_*.json'))
    test_files.sort()
    
    failure_patterns = {}
    success_patterns = {}
    
    for file in test_files[-5:]:  # 分析最近5个报告
        print(f"\n分析文件: {file}")
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            summary = data.get('summary', {})
            total = summary.get('total_tests', 0)
            successful = summary.get('successful_tests', 0)
            success_rate = summary.get('success_rate', '0%')
            
            print(f"  总测试: {total}, 成功: {successful}, 成功率: {success_rate}")
            
            # 分析失败模式
            failed_tests = []
            for result in data.get('detailed_results', []):
                if not result.get('success', True):
                    error_msg = result.get('error_message', 'No error message')
                    failed_tests.append({
                        'name': result.get('test_name', 'Unknown'),
                        'url': result.get('url', 'Unknown'),
                        'error': error_msg,
                        'time': result.get('processing_time', 'Unknown')
                    })
            
            if failed_tests:
                print(f"  失败的测试 ({len(failed_tests)}):")
                for test in failed_tests:
                    print(f"    - {test['name']}: {test['error']}")
                    
                # 统计错误类型
                for test in failed_tests:
                    error_type = test['error']
                    if error_type not in failure_patterns:
                        failure_patterns[error_type] = 0
                    failure_patterns[error_type] += 1
            else:
                print("  ✓ 所有测试都成功")
                
        except Exception as e:
            print(f"  错误读取文件: {e}")
    
    print(f"\n=== 失败模式统计 ===")
    for error_type, count in failure_patterns.items():
        print(f"  '{error_type}': {count} 次")
    
    return failure_patterns

def analyze_api_logs():
    """分析API日志中的错误信息"""
    
    print("\n=== 分析API日志中的错误信息 ===")
    
    try:
        with open('api_logs.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"日志总行数: {len(lines)}")
        
        # 查找错误相关的行
        error_lines = []
        validation_errors = []
        task_errors = []
        
        for i, line in enumerate(lines):
            if 'ERROR' in line or 'ValidationError' in line:
                error_lines.append((i+1, line.strip()))
            
            if 'ValidationError' in line and 'TaskStatusDTO' in line:
                validation_errors.append((i+1, line.strip()))
            
            if 'Task failed' in line:
                task_errors.append((i+1, line.strip()))
        
        print(f"\n错误行数: {len(error_lines)}")
        print(f"TaskStatusDTO验证错误: {len(validation_errors)}")
        print(f"任务失败错误: {len(task_errors)}")
        
        if validation_errors:
            print(f"\n=== TaskStatusDTO验证错误详情 ===")
            for line_num, line in validation_errors[:3]:  # 显示前3个
                print(f"  行{line_num}: {line}")
        
        if task_errors:
            print(f"\n=== 任务失败错误详情 ===")
            for line_num, line in task_errors[:3]:  # 显示前3个
                print(f"  行{line_num}: {line}")
        
        # 查找具体的ValidationError详情
        validation_details = []
        for i, line in enumerate(lines):
            if 'created_at' in line and 'Field required' in line:
                validation_details.append((i+1, line.strip()))
            if 'updated_at' in line and 'Field required' in line:
                validation_details.append((i+1, line.strip()))
        
        if validation_details:
            print(f"\n=== 字段验证错误详情 ===")
            for line_num, line in validation_details:
                print(f"  行{line_num}: {line}")
                
    except FileNotFoundError:
        print("  未找到api_logs.txt文件")
    except Exception as e:
        print(f"  读取日志文件错误: {e}")

def analyze_task_status_issue():
    """分析TaskStatusDTO的问题"""
    
    print("\n=== 分析TaskStatusDTO问题 ===")
    
    try:
        from literature_parser_backend.models.task import TaskStatusDTO, TaskExecutionStatus
        
        # 检查TaskStatusDTO的字段
        fields = TaskStatusDTO.model_fields
        
        print("TaskStatusDTO必需字段:")
        required_fields = []
        optional_fields = []
        
        for field_name, field_info in fields.items():
            if hasattr(field_info, 'is_required') and field_info.is_required():
                required_fields.append(field_name)
            else:
                # 检查默认值
                if hasattr(field_info, 'default') and field_info.default is not None:
                    optional_fields.append(f"{field_name} (有默认值)")
                else:
                    # 进一步检查Field定义
                    annotation = field_info.annotation
                    if hasattr(annotation, '__origin__') and annotation.__origin__ is type(None):
                        optional_fields.append(f"{field_name} (可选)")
                    else:
                        required_fields.append(field_name)
        
        print(f"  必需字段 ({len(required_fields)}):")
        for field in required_fields:
            print(f"    - {field}")
            
        print(f"  可选字段 ({len(optional_fields)}):")
        for field in optional_fields:
            print(f"    - {field}")
        
        # 检查是否有created_at/updated_at
        has_created_at = 'created_at' in fields
        has_updated_at = 'updated_at' in fields
        
        print(f"\n时间字段检查:")
        print(f"  created_at: {'存在' if has_created_at else '不存在'}")
        print(f"  updated_at: {'存在' if has_updated_at else '不存在'}")
        
        if not has_created_at and not has_updated_at:
            print("  ✓ 确认TaskStatusDTO没有时间字段")
            print("  这说明错误来自其他地方试图传递这些字段")
        
    except ImportError as e:
        print(f"  导入错误: {e}")
    except Exception as e:
        print(f"  分析错误: {e}")

def find_task_status_usage():
    """查找TaskStatusDTO的使用位置"""
    
    print("\n=== 查找TaskStatusDTO使用位置 ===")
    
    import subprocess
    
    try:
        # 使用grep查找TaskStatusDTO的使用
        result = subprocess.run([
            'grep', '-r', '-n', 'TaskStatusDTO', 
            'literature_parser_backend/',
            '--include=*.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            print(f"找到 {len(lines)} 个使用位置:")
            
            for line in lines[:10]:  # 显示前10个
                print(f"  {line}")
                
            # 查找可能有问题的模式
            problematic_patterns = []
            for line in lines:
                if '**' in line and 'TaskStatusDTO' in line:
                    problematic_patterns.append(line)
            
            if problematic_patterns:
                print(f"\n可能有问题的使用模式 ({len(problematic_patterns)}):")
                for pattern in problematic_patterns:
                    print(f"  {pattern}")
        else:
            print("  未找到TaskStatusDTO的使用")
            
    except Exception as e:
        print(f"  搜索错误: {e}")

def suggest_solutions():
    """建议解决方案"""
    
    print("\n=== 建议的解决方案 ===")
    
    print("1. TaskStatusDTO验证错误:")
    print("   - 问题：某个地方传递了包含created_at/updated_at的数据给TaskStatusDTO")
    print("   - 解决：检查所有创建TaskStatusDTO的地方，确保只传递正确的字段")
    print("   - 可能位置：tasks.py中的get_unified_status方法")
    
    print("\n2. 'Unknown error'问题:")
    print("   - 问题：Celery任务失败但错误信息没有正确传递")
    print("   - 解决：改进错误处理和日志记录")
    print("   - 需要检查：worker代码中的异常处理")
    
    print("\n3. 调试建议:")
    print("   - 启用更详细的日志记录")
    print("   - 添加try-catch块来捕获具体错误")
    print("   - 检查Celery worker的日志")
    print("   - 验证数据库连接和外部服务状态")

if __name__ == "__main__":
    print("文献解析失败分析报告")
    print("=" * 50)
    
    failure_patterns = analyze_test_reports()
    analyze_api_logs()
    analyze_task_status_issue()
    find_task_status_usage()
    suggest_solutions()
    
    print(f"\n=== 总结 ===")
    print("基于分析，主要问题包括:")
    print("1. TaskStatusDTO验证错误 - 字段不匹配")
    print("2. 任务失败时错误信息不明确")
    print("3. 需要改进错误处理和日志记录")



