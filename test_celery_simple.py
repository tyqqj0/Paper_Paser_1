#!/usr/bin/env python3
"""
简化的Celery测试脚本
"""

import time
import requests
from literature_parser_backend.worker.celery_app import celery_app
from literature_parser_backend.worker.tasks import process_literature_task

def test_celery_connection():
    """测试Celery连接"""
    print("🔍 测试Celery连接...")
    
    try:
        # 测试broker连接
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if stats:
            print("✅ Celery broker连接正常")
            print(f"   活跃workers: {list(stats.keys())}")
            return True
        else:
            print("❌ 无法连接到Celery broker")
            return False
            
    except Exception as e:
        print(f"❌ Celery连接错误: {e}")
        return False

def test_task_registration():
    """测试任务注册"""
    print("\n🔍 测试任务注册...")
    
    # 检查任务是否已注册
    registered_tasks = list(celery_app.tasks.keys())
    print(f"   已注册任务: {registered_tasks}")
    
    if "process_literature_task" in registered_tasks:
        print("✅ process_literature_task 已正确注册")
        return True
    else:
        print("❌ process_literature_task 未注册")
        return False

def test_task_submission():
    """测试任务提交"""
    print("\n🔍 测试任务提交...")
    
    try:
        # 提交一个简单的测试任务
        test_data = {
            "url": "http://example.com/test.pdf",
            "title": "Test Paper"
        }
        
        result = process_literature_task.delay(test_data)
        print(f"✅ 任务提交成功")
        print(f"   任务ID: {result.id}")
        print(f"   任务状态: {result.status}")
        
        return result.id
        
    except Exception as e:
        print(f"❌ 任务提交失败: {e}")
        return None

def test_task_monitoring(task_id):
    """测试任务监控"""
    if not task_id:
        return False
    
    print(f"\n🔍 监控任务 {task_id}...")
    
    try:
        # 通过API查询任务状态
        for i in range(10):  # 最多检查10次
            response = requests.get(f"http://localhost:8000/api/task/{task_id}", timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status')
                progress = result.get('progress_percentage', 0)
                
                print(f"   第{i+1}次检查: 状态={status}, 进度={progress}%")
                
                if status == 'success':
                    print("✅ 任务成功完成")
                    return True
                elif status == 'failure':
                    print("❌ 任务执行失败")
                    return False
                
                time.sleep(3)  # 等待3秒
            else:
                print(f"❌ API查询失败: {response.status_code}")
                return False
        
        print("⏰ 任务监控超时")
        return False
        
    except Exception as e:
        print(f"❌ 任务监控异常: {e}")
        return False

def main():
    """主函数"""
    print("🧪 Celery 系统测试")
    print("=" * 50)
    
    # 1. 测试连接
    if not test_celery_connection():
        print("\n❌ Celery连接失败，请检查Redis和Worker状态")
        return
    
    # 2. 测试任务注册
    if not test_task_registration():
        print("\n❌ 任务注册失败")
        return
    
    # 3. 测试任务提交
    task_id = test_task_submission()
    if not task_id:
        print("\n❌ 任务提交失败")
        return
    
    # 4. 测试任务监控
    success = test_task_monitoring(task_id)
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试通过！Celery系统正常工作")
    else:
        print("❌ 测试失败，请检查Worker日志")
        print("   docker logs literature_parser_backend-worker-1")

if __name__ == "__main__":
    main() 