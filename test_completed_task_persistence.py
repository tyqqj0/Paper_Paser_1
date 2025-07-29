#!/usr/bin/env python3
"""
测试已完成任务的持久化和查询机制

模拟前端断开连接后重新连接，验证任务状态是否能正确查询
"""

import requests
import json
import time
from typing import Dict, Any, Optional


class CompletedTaskTester:
    """已完成任务测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    def submit_task(self, source_data: Dict[str, Any]) -> Optional[str]:
        """提交一个文献处理任务"""
        try:
            response = requests.post(
                f"{self.base_url}/api/literature",
                json={"source": source_data},
                timeout=10
            )
            
            if response.status_code == 202:
                task_id = response.json().get("task_id")
                print(f"✅ 任务提交成功，task_id: {task_id}")
                return task_id
            elif response.status_code == 200:
                # 文献已存在，直接返回
                literature_id = response.json().get("literature_id")
                print(f"📚 文献已存在，literature_id: {literature_id}")
                return None
            else:
                print(f"❌ 任务提交失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 任务提交异常: {e}")
            return None
    
    def wait_for_completion(self, task_id: str, max_wait_seconds: int = 120) -> Dict[str, Any]:
        """等待任务完成"""
        print(f"⏳ 等待任务 {task_id} 完成...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            try:
                response = requests.get(
                    f"{self.base_url}/api/task/{task_id}",
                    timeout=5
                )
                
                if response.status_code == 200:
                    status_data = response.json()
                    execution_status = status_data.get("execution_status", "unknown")
                    
                    print(f"📊 当前状态: {execution_status}, 进度: {status_data.get('overall_progress', 0)}%")
                    
                    if execution_status in ["completed", "failed"]:
                        print(f"🎯 任务完成，最终状态: {execution_status}")
                        return status_data
                        
                else:
                    print(f"⚠️ 查询状态失败: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️ 查询状态异常: {e}")
            
            time.sleep(3)
        
        print(f"⏰ 任务在 {max_wait_seconds} 秒内未完成")
        return {}
    
    def simulate_disconnect_reconnect(self, task_id: str, disconnect_seconds: int = 30):
        """模拟前端断开连接后重新连接"""
        print(f"\n🔌 模拟断开连接 {disconnect_seconds} 秒...")
        time.sleep(disconnect_seconds)
        print("🔗 重新连接，查询任务状态...")
        
        try:
            response = requests.get(
                f"{self.base_url}/api/task/{task_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                status_data = response.json()
                print("✅ 重连后成功查询到任务状态:")
                print(f"   - 执行状态: {status_data.get('execution_status')}")
                print(f"   - 结果类型: {status_data.get('result_type')}")
                print(f"   - 文献ID: {status_data.get('literature_id')}")
                print(f"   - 整体进度: {status_data.get('overall_progress')}%")
                print(f"   - 当前阶段: {status_data.get('current_stage')}")
                
                # 如果有文献ID，尝试获取文献详情
                literature_id = status_data.get('literature_id')
                if literature_id:
                    self.verify_literature_access(literature_id)
                
                return status_data
            else:
                print(f"❌ 重连后查询失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 重连查询异常: {e}")
            return None
    
    def verify_literature_access(self, literature_id: str):
        """验证文献数据是否可以正常访问"""
        try:
            response = requests.get(
                f"{self.base_url}/api/literature/{literature_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                literature_data = response.json()
                print("📖 文献数据访问成功:")
                print(f"   - 标题: {literature_data.get('metadata', {}).get('title', 'N/A')}")
                print(f"   - 作者数: {len(literature_data.get('metadata', {}).get('authors', []))}")
                print(f"   - 参考文献数: {len(literature_data.get('references', []))}")
                return True
            else:
                print(f"❌ 文献数据访问失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 文献数据访问异常: {e}")
            return False
    
    def test_task_persistence_after_completion(self):
        """测试任务完成后的持久化机制"""
        print("=" * 60)
        print("🧪 测试：任务完成后的持久化和查询机制")
        print("=" * 60)
        
        # 1. 提交一个新任务
        source_data = {
            "url": "https://arxiv.org/abs/1706.03762",  # Attention Is All You Need
            "source_type": "arxiv"
        }
        
        task_id = self.submit_task(source_data)
        if not task_id:
            print("❌ 无法进行测试，任务提交失败或文献已存在")
            return False
        
        # 2. 等待任务完成
        completion_status = self.wait_for_completion(task_id)
        if not completion_status:
            print("❌ 任务未能在预期时间内完成")
            return False
        
        # 3. 模拟前端断开连接
        reconnect_status = self.simulate_disconnect_reconnect(task_id, 10)
        if not reconnect_status:
            print("❌ 重连后无法查询任务状态")
            return False
        
        # 4. 测试长时间后的查询（模拟更长的断开时间）
        print(f"\n⏰ 测试长时间断开后的查询（等待30秒）...")
        time.sleep(30)
        
        final_status = self.simulate_disconnect_reconnect(task_id, 0)
        if final_status:
            print("✅ 长时间断开后仍能正确查询任务状态")
            return True
        else:
            print("❌ 长时间断开后无法查询任务状态")
            return False


def main():
    """主测试函数"""
    tester = CompletedTaskTester()
    
    # 测试任务持久化机制
    success = tester.test_task_persistence_after_completion()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 所有测试通过！任务持久化机制工作正常")
    else:
        print("💥 测试失败！任务持久化机制存在问题")
    print("=" * 60)


if __name__ == "__main__":
    main()
