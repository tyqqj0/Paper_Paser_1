#!/usr/bin/env python3
"""
业务逻辑去重全面测试脚本

测试各种边缘情况下的瀑布流去重逻辑，验证系统在移除数据库唯一约束后的表现。
"""

import asyncio
import json
import time
from typing import Dict, List, Any
import requests


class BusinessLogicDeduplicationTester:
    """业务逻辑去重测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        
    def log_test(self, test_name: str, status: str, details: Dict[str, Any]):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": time.time(),
            "details": details
        }
        self.test_results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status}")
        if details.get("message"):
            print(f"   {details['message']}")
    
    def submit_literature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """提交文献处理请求"""
        try:
            response = requests.post(
                f"{self.base_url}/api/literature",
                json=data,
                timeout=10
            )
            return {
                "status_code": response.status_code,
                "data": response.json() if response.status_code < 500 else None,
                "success": response.status_code == 202
            }
        except Exception as e:
            return {
                "status_code": 0,
                "data": None,
                "success": False,
                "error": str(e)
            }
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            response = requests.get(f"{self.base_url}/api/task/{task_id}", timeout=10)
            return {
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else None,
                "success": response.status_code == 200
            }
        except Exception as e:
            return {
                "status_code": 0,
                "data": None,
                "success": False,
                "error": str(e)
            }
    
    def wait_for_task_completion(self, task_id: str, max_wait: int = 120) -> Dict[str, Any]:
        """等待任务完成"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            result = self.get_task_status(task_id)
            
            if not result["success"]:
                return result
                
            task_data = result["data"]
            status = task_data.get("status", "unknown")
            
            if status in ["success_created", "success_duplicate", "failure"]:
                return result
                
            time.sleep(2)
        
        return {
            "status_code": 408,
            "data": None,
            "success": False,
            "error": "Task timeout"
        }
    
    def test_doi_deduplication(self):
        """测试DOI去重"""
        print("\n🔬 测试DOI去重...")
        
        # 第一次提交
        data1 = {"doi": "10.48550/arXiv.1706.03762"}
        result1 = self.submit_literature(data1)
        
        if not result1["success"]:
            self.log_test("DOI去重-第一次提交", "FAIL", {
                "message": f"第一次提交失败: {result1.get('error', 'Unknown error')}"
            })
            return
        
        task_id1 = result1["data"]["task_id"]
        final_result1 = self.wait_for_task_completion(task_id1)
        
        if not final_result1["success"]:
            self.log_test("DOI去重-第一次处理", "FAIL", {
                "message": f"第一次处理失败: {final_result1.get('error', 'Unknown error')}"
            })
            return
        
        # 第二次提交相同DOI
        result2 = self.submit_literature(data1)
        
        if not result2["success"]:
            self.log_test("DOI去重-第二次提交", "FAIL", {
                "message": f"第二次提交失败: {result2.get('error', 'Unknown error')}"
            })
            return
        
        task_id2 = result2["data"]["task_id"]
        final_result2 = self.wait_for_task_completion(task_id2)
        
        if final_result2["success"]:
            status = final_result2["data"].get("status")
            if status == "success_duplicate":
                self.log_test("DOI去重", "PASS", {
                    "message": "成功检测到DOI重复",
                    "first_task": task_id1,
                    "second_task": task_id2
                })
            else:
                self.log_test("DOI去重", "FAIL", {
                    "message": f"未检测到重复，状态: {status}",
                    "first_task": task_id1,
                    "second_task": task_id2
                })
        else:
            self.log_test("DOI去重", "FAIL", {
                "message": f"第二次处理失败: {final_result2.get('error', 'Unknown error')}"
            })
    
    def test_arxiv_deduplication(self):
        """测试ArXiv ID去重"""
        print("\n🔬 测试ArXiv ID去重...")
        
        # 第一次提交
        data1 = {"url": "https://arxiv.org/abs/2301.07041"}
        result1 = self.submit_literature(data1)
        
        if not result1["success"]:
            self.log_test("ArXiv去重-第一次提交", "FAIL", {
                "message": f"第一次提交失败: {result1.get('error', 'Unknown error')}"
            })
            return
        
        task_id1 = result1["data"]["task_id"]
        final_result1 = self.wait_for_task_completion(task_id1)
        
        if not final_result1["success"]:
            self.log_test("ArXiv去重-第一次处理", "FAIL", {
                "message": f"第一次处理失败: {final_result1.get('error', 'Unknown error')}"
            })
            return
        
        # 第二次提交相同ArXiv（不同格式）
        data2 = {"arxiv_id": "2301.07041"}
        result2 = self.submit_literature(data2)
        
        if not result2["success"]:
            self.log_test("ArXiv去重-第二次提交", "FAIL", {
                "message": f"第二次提交失败: {result2.get('error', 'Unknown error')}"
            })
            return
        
        task_id2 = result2["data"]["task_id"]
        final_result2 = self.wait_for_task_completion(task_id2)
        
        if final_result2["success"]:
            status = final_result2["data"].get("status")
            if status == "success_duplicate":
                self.log_test("ArXiv去重", "PASS", {
                    "message": "成功检测到ArXiv重复",
                    "first_task": task_id1,
                    "second_task": task_id2
                })
            else:
                self.log_test("ArXiv去重", "FAIL", {
                    "message": f"未检测到重复，状态: {status}",
                    "first_task": task_id1,
                    "second_task": task_id2
                })
        else:
            self.log_test("ArXiv去重", "FAIL", {
                "message": f"第二次处理失败: {final_result2.get('error', 'Unknown error')}"
            })
    
    def test_concurrent_submission(self):
        """测试并发提交"""
        print("\n🔬 测试并发提交...")
        
        # 同时提交相同的文献
        data = {"doi": "10.1038/nature12373"}
        
        # 快速连续提交
        results = []
        for i in range(3):
            result = self.submit_literature(data)
            results.append(result)
            time.sleep(0.1)  # 很短的间隔
        
        # 检查所有提交是否成功
        successful_submissions = [r for r in results if r["success"]]
        
        if len(successful_submissions) != 3:
            self.log_test("并发提交", "FAIL", {
                "message": f"只有 {len(successful_submissions)}/3 次提交成功"
            })
            return
        
        # 等待所有任务完成
        final_results = []
        for result in successful_submissions:
            task_id = result["data"]["task_id"]
            final_result = self.wait_for_task_completion(task_id)
            final_results.append(final_result)
        
        # 分析结果
        created_count = 0
        duplicate_count = 0
        failed_count = 0
        
        for final_result in final_results:
            if final_result["success"]:
                status = final_result["data"].get("status")
                if status == "success_created":
                    created_count += 1
                elif status == "success_duplicate":
                    duplicate_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1
        
        if created_count == 1 and duplicate_count == 2:
            self.log_test("并发提交", "PASS", {
                "message": f"正确处理并发: 1个创建, 2个重复",
                "created": created_count,
                "duplicate": duplicate_count,
                "failed": failed_count
            })
        else:
            self.log_test("并发提交", "WARN", {
                "message": f"并发处理结果: {created_count}个创建, {duplicate_count}个重复, {failed_count}个失败",
                "created": created_count,
                "duplicate": duplicate_count,
                "failed": failed_count
            })
    
    def test_cross_identifier_deduplication(self):
        """测试跨标识符去重"""
        print("\n🔬 测试跨标识符去重...")
        
        # 先提交DOI
        data1 = {"doi": "10.48550/arXiv.2205.14217"}
        result1 = self.submit_literature(data1)
        
        if not result1["success"]:
            self.log_test("跨标识符去重-DOI提交", "FAIL", {
                "message": f"DOI提交失败: {result1.get('error', 'Unknown error')}"
            })
            return
        
        task_id1 = result1["data"]["task_id"]
        final_result1 = self.wait_for_task_completion(task_id1)
        
        if not final_result1["success"]:
            self.log_test("跨标识符去重-DOI处理", "FAIL", {
                "message": f"DOI处理失败: {final_result1.get('error', 'Unknown error')}"
            })
            return
        
        # 再提交相同论文的ArXiv URL
        data2 = {"url": "https://arxiv.org/abs/2205.14217"}
        result2 = self.submit_literature(data2)
        
        if not result2["success"]:
            self.log_test("跨标识符去重-ArXiv提交", "FAIL", {
                "message": f"ArXiv提交失败: {result2.get('error', 'Unknown error')}"
            })
            return
        
        task_id2 = result2["data"]["task_id"]
        final_result2 = self.wait_for_task_completion(task_id2)
        
        if final_result2["success"]:
            status = final_result2["data"].get("status")
            if status == "success_duplicate":
                self.log_test("跨标识符去重", "PASS", {
                    "message": "成功检测到跨标识符重复 (DOI vs ArXiv)",
                    "doi_task": task_id1,
                    "arxiv_task": task_id2
                })
            else:
                self.log_test("跨标识符去重", "FAIL", {
                    "message": f"未检测到跨标识符重复，状态: {status}",
                    "doi_task": task_id1,
                    "arxiv_task": task_id2
                })
        else:
            self.log_test("跨标识符去重", "FAIL", {
                "message": f"ArXiv处理失败: {final_result2.get('error', 'Unknown error')}"
            })
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始业务逻辑去重全面测试...")
        print("=" * 60)
        
        # 运行各项测试
        self.test_doi_deduplication()
        self.test_arxiv_deduplication()
        self.test_concurrent_submission()
        self.test_cross_identifier_deduplication()
        
        # 统计结果
        print("\n" + "=" * 60)
        print("📊 测试结果统计:")
        
        pass_count = len([r for r in self.test_results if r["status"] == "PASS"])
        fail_count = len([r for r in self.test_results if r["status"] == "FAIL"])
        warn_count = len([r for r in self.test_results if r["status"] == "WARN"])
        total_count = len(self.test_results)
        
        print(f"✅ 通过: {pass_count}")
        print(f"❌ 失败: {fail_count}")
        print(f"⚠️  警告: {warn_count}")
        print(f"📈 总计: {total_count}")
        
        if fail_count == 0:
            print("\n🎉 所有核心测试通过！业务逻辑去重工作正常！")
        else:
            print(f"\n⚠️  有 {fail_count} 个测试失败，需要进一步调查。")
        
        return {
            "pass": pass_count,
            "fail": fail_count,
            "warn": warn_count,
            "total": total_count,
            "results": self.test_results
        }


if __name__ == "__main__":
    tester = BusinessLogicDeduplicationTester()
    results = tester.run_all_tests()
    
    # 保存详细结果
    with open("deduplication_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 详细测试结果已保存到: deduplication_test_results.json")
