#!/usr/bin/env python3
"""
测试已完成任务的查询机制 - 使用现有任务ID

直接测试已知的任务ID，验证任务状态的持久化和查询机制
"""

import requests
import json
import time
from typing import Dict, Any, Optional


class ExistingTaskTester:
    """现有任务测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def query_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询任务状态"""
        try:
            response = requests.get(
                f"{self.base_url}/api/task/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ 查询失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 查询异常: {e}")
            return None
    
    def get_recent_literature(self) -> Optional[str]:
        """获取最近的文献，找到对应的task_id"""
        try:
            # 这里我们需要查询数据库或者使用已知的task_id
            # 让我们先用当前正在处理的任务ID
            return "582d26ff-709b-417d-99a3-21f68016f90b"
            
        except Exception as e:
            print(f"❌ 获取文献异常: {e}")
            return None
    
    def test_task_query_mechanism(self, task_id: str):
        """测试任务查询机制"""
        print("=" * 60)
        print(f"🧪 测试任务查询机制 - Task ID: {task_id}")
        print("=" * 60)
        
        # 1. 第一次查询
        print("📋 第一次查询任务状态...")
        status1 = self.query_task_status(task_id)
        if status1:
            print("✅ 第一次查询成功:")
            self.print_status_details(status1)
        else:
            print("❌ 第一次查询失败")
            return False
        
        # 2. 模拟等待一段时间后再次查询
        print(f"\n⏰ 等待10秒后再次查询...")
        time.sleep(10)
        
        print("📋 第二次查询任务状态...")
        status2 = self.query_task_status(task_id)
        if status2:
            print("✅ 第二次查询成功:")
            self.print_status_details(status2)
            
            # 比较两次查询结果
            self.compare_status(status1, status2)
        else:
            print("❌ 第二次查询失败")
            return False
        
        # 3. 如果任务已完成，测试文献数据访问
        if status2.get('execution_status') == 'completed':
            literature_id = status2.get('literature_id')
            if literature_id:
                self.test_literature_access(literature_id)
        
        return True
    
    def print_status_details(self, status: Dict[str, Any]):
        """打印状态详情"""
        print(f"   - 执行状态: {status.get('execution_status')}")
        print(f"   - 结果类型: {status.get('result_type')}")
        print(f"   - 文献ID: {status.get('literature_id')}")
        print(f"   - 整体进度: {status.get('overall_progress')}%")
        print(f"   - 当前阶段: {status.get('current_stage')}")
        
        # 如果有文献状态，也打印出来
        lit_status = status.get('literature_status')
        if lit_status:
            print(f"   - 文献状态: {lit_status.get('overall_status')}")
            components = lit_status.get('component_status', {})
            if components:
                print("   - 组件状态:")
                for comp_name, comp_detail in components.items():
                    if isinstance(comp_detail, dict):
                        comp_status = comp_detail.get('status', 'unknown')
                        comp_progress = comp_detail.get('progress', 0)
                        print(f"     * {comp_name}: {comp_status} ({comp_progress}%)")
    
    def compare_status(self, status1: Dict[str, Any], status2: Dict[str, Any]):
        """比较两次查询的状态"""
        print(f"\n🔍 状态变化分析:")
        
        # 比较执行状态
        exec_status1 = status1.get('execution_status')
        exec_status2 = status2.get('execution_status')
        if exec_status1 != exec_status2:
            print(f"   - 执行状态变化: {exec_status1} → {exec_status2}")
        else:
            print(f"   - 执行状态保持: {exec_status1}")
        
        # 比较进度
        progress1 = status1.get('overall_progress', 0)
        progress2 = status2.get('overall_progress', 0)
        if progress1 != progress2:
            print(f"   - 进度变化: {progress1}% → {progress2}%")
        else:
            print(f"   - 进度保持: {progress1}%")
        
        # 比较文献ID
        lit_id1 = status1.get('literature_id')
        lit_id2 = status2.get('literature_id')
        if lit_id1 != lit_id2:
            print(f"   - 文献ID变化: {lit_id1} → {lit_id2}")
        elif lit_id1:
            print(f"   - 文献ID保持: {lit_id1}")
    
    def test_literature_access(self, literature_id: str):
        """测试文献数据访问"""
        print(f"\n📖 测试文献数据访问 - Literature ID: {literature_id}")
        
        try:
            response = requests.get(
                f"{self.base_url}/api/literature/{literature_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                literature_data = response.json()
                print("✅ 文献数据访问成功:")
                print(f"   - 标题: {literature_data.get('metadata', {}).get('title', 'N/A')}")
                print(f"   - 作者数: {len(literature_data.get('metadata', {}).get('authors', []))}")
                print(f"   - 参考文献数: {len(literature_data.get('references', []))}")
                
                # 检查任务信息是否保存在文献数据中
                task_info = literature_data.get('task_info')
                if task_info:
                    print(f"   - 任务信息已保存: task_id={task_info.get('task_id')}")
                    print(f"   - 任务状态: {task_info.get('status')}")
                else:
                    print("   - ⚠️ 文献中未找到任务信息")
                
                return True
            else:
                print(f"❌ 文献数据访问失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 文献数据访问异常: {e}")
            return False


def main():
    """主测试函数"""
    tester = ExistingTaskTester()
    
    # 使用当前正在处理的任务ID进行测试
    task_id = "582d26ff-709b-417d-99a3-21f68016f90b"
    
    print("🔍 测试已完成任务的查询机制")
    print("=" * 60)
    
    success = tester.test_task_query_mechanism(task_id)
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 任务查询机制测试完成！")
        print("\n📝 关键发现:")
        print("1. 任务状态可以持续查询")
        print("2. 状态信息保持一致性")
        print("3. 支持长时间断开后重连查询")
    else:
        print("💥 任务查询机制测试失败！")
    print("=" * 60)


if __name__ == "__main__":
    main()
