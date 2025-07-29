#!/usr/bin/env python3
"""
并发性能测试脚本

测试系统在高并发情况下的表现，包括：
1. 并发提交相同文献测试去重功能
2. 并发提交不同文献测试处理能力
3. 系统负载测试

使用方法:
    python test_concurrency.py --test dedup --count 10     # 测试去重，10个并发
    python test_concurrency.py --test load --count 20      # 负载测试，20个并发
    python test_concurrency.py --test mixed --count 15     # 混合测试，15个并发
"""

import argparse
import asyncio
import json
import random
import sys
import time
from datetime import datetime
from typing import List, Dict, Any

import aiohttp
from loguru import logger


class ConcurrencyTester:
    """并发测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.results = []
    
    async def initialize(self):
        """初始化HTTP会话"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)  # 5分钟超时
        )
        logger.info("✅ HTTP会话初始化成功")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
    
    async def submit_literature(self, literature_data: Dict[str, Any]) -> Dict[str, Any]:
        """提交文献处理请求"""
        url = f"{self.base_url}/api/literature/"
        
        start_time = time.time()
        
        try:
            async with self.session.post(url, json=literature_data) as response:
                end_time = time.time()
                
                result = {
                    "status_code": response.status,
                    "response_time": round(end_time - start_time, 3),
                    "success": response.status in [200, 201, 202],  # 202是异步任务创建成功
                    "literature_data": literature_data,
                    "timestamp": datetime.now().isoformat(),
                }

                if response.status in [200, 201, 202]:
                    response_data = await response.json()
                    result["task_id"] = response_data.get("task_id")
                    result["literature_id"] = response_data.get("literature_id")
                    result["message"] = response_data.get("message")
                else:
                    result["error"] = await response.text()
                
                return result
                
        except Exception as e:
            end_time = time.time()
            return {
                "status_code": 0,
                "response_time": round(end_time - start_time, 3),
                "success": False,
                "error": str(e),
                "literature_data": literature_data,
                "timestamp": datetime.now().isoformat(),
            }
    
    async def test_deduplication(self, concurrent_count: int = 10) -> List[Dict[str, Any]]:
        """测试去重功能 - 并发提交相同文献"""
        logger.info(f"🔄 开始去重测试，并发数: {concurrent_count}")
        
        # 使用相同的文献数据
        literature_data = {
            "url": "https://doi.org/10.1038/nature12373",
            "title": "Deep learning test paper",
            "authors": ["Test Author"]
        }
        
        # 创建并发任务
        tasks = []
        for i in range(concurrent_count):
            task = asyncio.create_task(
                self.submit_literature(literature_data),
                name=f"dedup_test_{i}"
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "task_name": f"dedup_test_{i}",
                    "success": False,
                    "error": str(result),
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                result["task_name"] = f"dedup_test_{i}"
                processed_results.append(result)
        
        return processed_results
    
    async def test_load(self, concurrent_count: int = 20) -> List[Dict[str, Any]]:
        """负载测试 - 并发提交不同文献"""
        logger.info(f"📊 开始负载测试，并发数: {concurrent_count}")
        
        # 生成不同的文献数据
        literature_list = []
        for i in range(concurrent_count):
            literature_data = {
                "url": f"https://example.com/paper_{i}",
                "title": f"Test Paper {i}: Concurrent Processing Analysis",
                "authors": [f"Test Author {i}"]
            }
            literature_list.append(literature_data)
        
        # 创建并发任务
        tasks = []
        for i, literature_data in enumerate(literature_list):
            task = asyncio.create_task(
                self.submit_literature(literature_data),
                name=f"load_test_{i}"
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "task_name": f"load_test_{i}",
                    "success": False,
                    "error": str(result),
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                result["task_name"] = f"load_test_{i}"
                processed_results.append(result)
        
        return processed_results
    
    async def test_mixed(self, concurrent_count: int = 15) -> List[Dict[str, Any]]:
        """混合测试 - 部分相同，部分不同的文献"""
        logger.info(f"🔀 开始混合测试，并发数: {concurrent_count}")
        
        literature_list = []
        
        # 30%相同文献（测试去重）
        duplicate_count = int(concurrent_count * 0.3)
        duplicate_data = {
            "url": "https://doi.org/10.1038/nature12373",
            "title": "Duplicate Test Paper",
            "authors": ["Duplicate Author"]
        }
        for i in range(duplicate_count):
            literature_list.append(duplicate_data)

        # 70%不同文献（测试负载）
        unique_count = concurrent_count - duplicate_count
        for i in range(unique_count):
            literature_data = {
                "url": f"https://example.com/unique_paper_{i}",
                "title": f"Unique Paper {i}: Mixed Test Analysis",
                "authors": [f"Unique Author {i}"]
            }
            literature_list.append(literature_data)
        
        # 随机打乱顺序
        random.shuffle(literature_list)
        
        # 创建并发任务
        tasks = []
        for i, literature_data in enumerate(literature_list):
            task = asyncio.create_task(
                self.submit_literature(literature_data),
                name=f"mixed_test_{i}"
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "task_name": f"mixed_test_{i}",
                    "success": False,
                    "error": str(result),
                    "timestamp": datetime.now().isoformat(),
                })
            else:
                result["task_name"] = f"mixed_test_{i}"
                processed_results.append(result)
        
        return processed_results
    
    def analyze_results(self, results: List[Dict[str, Any]], test_type: str):
        """分析测试结果"""
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r.get("success", False))
        failed_requests = total_requests - successful_requests
        
        response_times = [r.get("response_time", 0) for r in results if r.get("response_time")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0
        min_response_time = min(response_times) if response_times else 0
        
        # 统计不同的literature_id（用于去重测试）
        literature_ids = set()
        task_ids = set()
        for r in results:
            if r.get("literature_id"):
                literature_ids.add(r["literature_id"])
            if r.get("task_id"):
                task_ids.add(r["task_id"])
        
        print(f"\n📊 {test_type.upper()} 测试结果分析")
        print("="*60)
        print(f"总请求数: {total_requests}")
        print(f"成功请求: {successful_requests}")
        print(f"失败请求: {failed_requests}")
        print(f"成功率: {successful_requests/total_requests*100:.2f}%")
        print(f"平均响应时间: {avg_response_time:.3f}s")
        print(f"最大响应时间: {max_response_time:.3f}s")
        print(f"最小响应时间: {min_response_time:.3f}s")
        print(f"唯一文献ID数: {len(literature_ids)}")
        print(f"唯一任务ID数: {len(task_ids)}")
        
        if test_type == "dedup":
            print(f"去重效果: {len(literature_ids)} 个唯一文献 (期望: 1)")
            if len(literature_ids) == 1:
                print("✅ 去重功能正常")
            else:
                print("❌ 去重功能异常")
        
        # 显示失败的请求
        failed_results = [r for r in results if not r.get("success", False)]
        if failed_results:
            print(f"\n❌ 失败请求详情:")
            for i, result in enumerate(failed_results[:5]):  # 只显示前5个
                print(f"  {i+1}. {result.get('error', 'Unknown error')}")
        
        print("="*60)
    
    def export_results(self, results: List[Dict[str, Any]], test_type: str):
        """导出测试结果"""
        filename = f"concurrency_test_{test_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "test_type": test_type,
                    "timestamp": datetime.now().isoformat(),
                    "total_requests": len(results),
                    "results": results
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📁 测试结果已导出到: {filename}")
            
        except Exception as e:
            logger.error(f"导出结果失败: {e}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="并发性能测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
测试类型:
    dedup  - 去重测试：并发提交相同文献
    load   - 负载测试：并发提交不同文献  
    mixed  - 混合测试：部分相同部分不同的文献

使用示例:
    python test_concurrency.py --test dedup --count 10
    python test_concurrency.py --test load --count 20
    python test_concurrency.py --test mixed --count 15
        """
    )
    
    parser.add_argument(
        "--test", 
        choices=["dedup", "load", "mixed"],
        required=True,
        help="测试类型"
    )
    
    parser.add_argument(
        "--count", 
        type=int, 
        default=10,
        help="并发请求数量 (默认: 10)"
    )
    
    parser.add_argument(
        "--url", 
        default="http://localhost:8000",
        help="API基础URL (默认: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--export", 
        action="store_true", 
        help="导出测试结果到JSON文件"
    )
    
    args = parser.parse_args()
    
    tester = ConcurrencyTester(args.url)
    
    try:
        await tester.initialize()
        
        logger.info(f"🚀 开始 {args.test.upper()} 测试，并发数: {args.count}")
        start_time = time.time()
        
        if args.test == "dedup":
            results = await tester.test_deduplication(args.count)
        elif args.test == "load":
            results = await tester.test_load(args.count)
        elif args.test == "mixed":
            results = await tester.test_mixed(args.count)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        logger.info(f"✅ 测试完成，总耗时: {total_time:.2f}s")
        
        # 分析结果
        tester.analyze_results(results, args.test)
        
        # 导出结果
        if args.export:
            tester.export_results(results, args.test)
        
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        sys.exit(1)
    
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
