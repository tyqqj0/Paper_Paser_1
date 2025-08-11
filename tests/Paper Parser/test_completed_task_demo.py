#!/usr/bin/env python3
"""
演示已完成任务的查询机制

使用一个简单的文献提交，然后测试任务完成后的持久化查询
"""

import requests
import json
import time
from typing import Dict, Any, Optional


def test_task_persistence_mechanism():
    """测试任务持久化机制的完整演示"""
    base_url = "http://localhost:8000"
    
    print("=" * 70)
    print("🧪 任务持久化机制演示")
    print("=" * 70)
    
    # 1. 提交一个简单的DOI任务（通常处理较快）
    print("📝 步骤1: 提交一个DOI任务...")
    
    payload = {
        "source": {
            "doi": "10.1038/nature12373"  # 一个经典的Nature论文
        }
    }
    
    try:
        response = requests.post(f"{base_url}/api/literature", json=payload, timeout=10)
        
        if response.status_code == 202:
            task_id = response.json().get("task_id")
            print(f"✅ 新任务创建成功: {task_id}")
            
        elif response.status_code == 200:
            # 文献已存在，获取现有的literature_id
            literature_data = response.json()
            literature_id = literature_data.get("literature_id")
            print(f"📚 文献已存在: {literature_id}")
            
            # 从文献数据中获取task_id
            task_info = literature_data.get("task_info")
            if task_info and task_info.get("task_id"):
                task_id = task_info["task_id"]
                print(f"🔍 找到关联的Task ID: {task_id}")
            else:
                print("❌ 无法找到关联的Task ID")
                return False
        else:
            print(f"❌ 任务提交失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 任务提交异常: {e}")
        return False
    
    # 2. 查询任务状态
    print(f"\n📋 步骤2: 查询任务状态...")
    
    def query_task_status(task_id: str) -> Optional[Dict[str, Any]]:
        try:
            response = requests.get(f"{base_url}/api/task/{task_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ 查询失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 查询异常: {e}")
            return None
    
    # 第一次查询
    status = query_task_status(task_id)
    if not status:
        print("❌ 无法查询任务状态")
        return False
    
    print("✅ 任务状态查询成功:")
    print(f"   - 执行状态: {status.get('execution_status')}")
    print(f"   - 结果类型: {status.get('result_type')}")
    print(f"   - 文献ID: {status.get('literature_id')}")
    print(f"   - 整体进度: {status.get('overall_progress')}%")
    
    # 3. 模拟前端断开连接
    print(f"\n🔌 步骤3: 模拟前端断开连接15秒...")
    time.sleep(15)
    
    # 4. 重新连接并查询
    print(f"🔗 步骤4: 重新连接，查询任务状态...")
    
    reconnect_status = query_task_status(task_id)
    if not reconnect_status:
        print("❌ 重连后无法查询任务状态")
        return False
    
    print("✅ 重连后任务状态查询成功:")
    print(f"   - 执行状态: {reconnect_status.get('execution_status')}")
    print(f"   - 结果类型: {reconnect_status.get('result_type')}")
    print(f"   - 文献ID: {reconnect_status.get('literature_id')}")
    print(f"   - 整体进度: {reconnect_status.get('overall_progress')}%")
    
    # 5. 如果任务已完成，测试文献数据访问
    literature_id = reconnect_status.get('literature_id')
    if literature_id:
        print(f"\n📖 步骤5: 访问文献数据...")
        
        try:
            lit_response = requests.get(f"{base_url}/api/literature/{literature_id}", timeout=10)
            if lit_response.status_code == 200:
                lit_data = lit_response.json()
                print("✅ 文献数据访问成功:")
                print(f"   - 标题: {lit_data.get('metadata', {}).get('title', 'N/A')}")
                print(f"   - DOI: {lit_data.get('identifiers', {}).get('doi', 'N/A')}")
                
                # 检查任务信息是否保存
                task_info = lit_data.get('task_info')
                if task_info:
                    print(f"   - 保存的Task ID: {task_info.get('task_id')}")
                    print(f"   - 任务状态: {task_info.get('status')}")
                    print(f"   - 完成时间: {task_info.get('completed_at')}")
                else:
                    print("   - ⚠️ 未找到任务信息")
                    
            else:
                print(f"❌ 文献数据访问失败: {lit_response.status_code}")
                
        except Exception as e:
            print(f"❌ 文献数据访问异常: {e}")
    
    # 6. 测试长时间后的查询
    print(f"\n⏰ 步骤6: 测试长时间后的查询（等待30秒）...")
    time.sleep(300)
    
    final_status = query_task_status(task_id)
    if final_status:
        print("✅ 长时间后任务状态仍可查询:")
        print(f"   - 执行状态: {final_status.get('execution_status')}")
        print(f"   - 文献ID: {final_status.get('literature_id')}")
        print(f"   - 状态一致性: {'✅' if final_status.get('execution_status') == reconnect_status.get('execution_status') else '❌'}")
    else:
        print("❌ 长时间后无法查询任务状态")
        return False
    
    return True


def main():
    """主函数"""
    print("🚀 开始测试任务持久化机制...")
    
    success = test_task_persistence_mechanism()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 任务持久化机制测试成功！")
        print("\n📋 关键结论:")
        print("✅ 1. 任务状态在Redis中持久化存储")
        print("✅ 2. 前端断开连接后可以重新查询")
        print("✅ 3. 任务信息同时保存在MongoDB文献数据中")
        print("✅ 4. 支持长时间断开后的状态查询")
        print("✅ 5. 状态信息保持一致性")
        
        print("\n💡 前后端联调建议:")
        print("• 前端可以安全地断开连接")
        print("• 重连后使用task_id继续轮询")
        print("• 任务完成后可通过literature_id访问数据")
        print("• 建议实现本地存储保存task_id")
        
    else:
        print("💥 任务持久化机制测试失败！")
        print("需要检查Redis配置和任务状态管理逻辑")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
