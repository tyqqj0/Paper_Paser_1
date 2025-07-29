#!/usr/bin/env python3
"""
Worker并行处理能力测试脚本

专门测试Celery Worker的真实并行处理能力，而不是API提交能力。
通过监控任务的实际执行状态来评估Worker的并发处理性能。

使用方法:
    python test_worker_concurrency.py --count 16 --timeout 300    # 提交16个任务，监控5分钟
    python test_worker_concurrency.py --count 8 --quick           # 快速测试，使用简单任务
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import aiohttp
from loguru import logger


class WorkerConcurrencyTester:
    """Worker并发测试器"""
    
    def __init__(self, base_url: str = "http://api:8000"):
        self.base_url = base_url
        self.session = None
        self.submitted_tasks = []
        self.monitoring_data = []
    
    async def initialize(self):
        """初始化HTTP会话"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)
        )
        logger.info("✅ HTTP会话初始化成功")
    
    async def cleanup(self):
        """清理资源"""
        if self.session:
            await self.session.close()
    
    async def submit_task(self, task_data: Dict[str, Any]) -> Optional[str]:
        """提交单个任务并返回task_id"""
        url = f"{self.base_url}/api/literature/"
        
        try:
            async with self.session.post(url, json=task_data) as response:
                if response.status in [200, 201, 202]:
                    response_data = await response.json()
                    task_id = response_data.get("task_id")
                    if task_id:
                        logger.info(f"✅ 任务提交成功: {task_id}")
                        return task_id
                    else:
                        logger.error(f"❌ 响应中没有task_id: {response_data}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"❌ 任务提交失败 {response.status}: {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ 提交任务时出错: {e}")
            return None
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """获取任务状态"""
        url = f"{self.base_url}/api/task/{task_id}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {"error": f"HTTP {response.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def submit_batch_tasks(self, count: int, quick_mode: bool = False) -> List[str]:
        """批量提交任务"""
        logger.info(f"🚀 开始提交 {count} 个任务...")
        
        tasks = []
        task_ids = []
        
        for i in range(count):
            if quick_mode:
                # 快速模式：使用会快速失败的URL，减少处理时间
                task_data = {
                    "url": f"https://httpbin.org/status/404?task={i}",  # 会快速返回404
                    "title": f"Quick Test Task {i}",
                    "authors": [f"Test Author {i}"]
                }
            else:
                # 正常模式：使用真实但简单的任务
                task_data = {
                    "url": f"https://example.com/test_paper_{i}",
                    "title": f"Worker Concurrency Test Paper {i}",
                    "authors": [f"Test Author {i}"]
                }
            
            task = asyncio.create_task(
                self.submit_task(task_data),
                name=f"submit_task_{i}"
            )
            tasks.append(task)
        
        # 等待所有任务提交完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, str):  # task_id
                task_ids.append(result)
                self.submitted_tasks.append({
                    "task_id": result,
                    "submit_time": datetime.now(),
                    "task_index": i
                })
            elif isinstance(result, Exception):
                logger.error(f"任务 {i} 提交异常: {result}")
            else:
                logger.warning(f"任务 {i} 提交失败: {result}")
        
        logger.info(f"📊 成功提交 {len(task_ids)} / {count} 个任务")
        return task_ids
    
    async def monitor_tasks(self, task_ids: List[str], timeout_minutes: int = 10) -> Dict[str, Any]:
        """监控任务执行状态"""
        logger.info(f"👀 开始监控 {len(task_ids)} 个任务，超时 {timeout_minutes} 分钟")
        
        start_time = datetime.now()
        timeout_time = start_time + timedelta(minutes=timeout_minutes)
        
        task_status_history = {task_id: [] for task_id in task_ids}
        active_tasks = set(task_ids)
        completed_tasks = set()
        failed_tasks = set()
        
        max_concurrent_processing = 0
        processing_count_history = []
        
        while active_tasks and datetime.now() < timeout_time:
            current_time = datetime.now()
            processing_count = 0
            pending_count = 0
            
            # 检查所有活跃任务的状态
            status_tasks = []
            for task_id in list(active_tasks):
                status_tasks.append(self.get_task_status(task_id))
            
            statuses = await asyncio.gather(*status_tasks, return_exceptions=True)
            
            for task_id, status in zip(list(active_tasks), statuses):
                if isinstance(status, Exception):
                    logger.error(f"获取任务状态失败 {task_id}: {status}")
                    continue
                
                if "error" in status:
                    logger.warning(f"任务状态错误 {task_id}: {status['error']}")
                    continue
                
                # 记录状态历史
                status_info = {
                    "timestamp": current_time.isoformat(),
                    "status": status.get("status", "unknown"),
                    "execution_status": status.get("execution_status", "unknown")
                }
                task_status_history[task_id].append(status_info)
                
                # 统计当前状态
                execution_status = status.get("execution_status", "unknown")
                task_status = status.get("status", "unknown")
                
                if execution_status in ["processing", "in_progress"] or task_status in ["processing", "in_progress"]:
                    processing_count += 1
                elif execution_status == "pending" or task_status == "pending":
                    pending_count += 1
                elif execution_status in ["completed", "success"] or task_status in ["completed", "success"]:
                    completed_tasks.add(task_id)
                    active_tasks.remove(task_id)
                    logger.info(f"✅ 任务完成: {task_id}")
                elif execution_status in ["failed", "error"] or task_status in ["failed", "error"]:
                    failed_tasks.add(task_id)
                    active_tasks.remove(task_id)
                    logger.info(f"❌ 任务失败: {task_id}")
            
            # 更新最大并发处理数
            max_concurrent_processing = max(max_concurrent_processing, processing_count)
            
            # 记录处理数量历史
            processing_count_history.append({
                "timestamp": current_time.isoformat(),
                "processing": processing_count,
                "pending": pending_count,
                "completed": len(completed_tasks),
                "failed": len(failed_tasks),
                "active": len(active_tasks)
            })
            
            # 显示当前状态
            elapsed = (current_time - start_time).total_seconds()
            logger.info(f"⏱️  {elapsed:.0f}s | 处理中: {processing_count} | 等待中: {pending_count} | 已完成: {len(completed_tasks)} | 已失败: {len(failed_tasks)} | 剩余: {len(active_tasks)}")
            
            # 如果没有任务在处理且队列为空，可能需要等待
            if processing_count == 0 and pending_count == 0 and active_tasks:
                logger.warning("⚠️  没有任务在处理，可能所有任务都已完成或失败")
                break
            
            # 等待一段时间再检查
            await asyncio.sleep(5)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 汇总结果
        result = {
            "test_summary": {
                "total_tasks": len(task_ids),
                "completed_tasks": len(completed_tasks),
                "failed_tasks": len(failed_tasks),
                "timeout_tasks": len(active_tasks),
                "success_rate": len(completed_tasks) / len(task_ids) * 100,
                "total_time_seconds": total_time,
                "max_concurrent_processing": max_concurrent_processing
            },
            "task_status_history": task_status_history,
            "processing_count_history": processing_count_history,
            "completed_task_ids": list(completed_tasks),
            "failed_task_ids": list(failed_tasks),
            "timeout_task_ids": list(active_tasks)
        }
        
        return result
    
    def analyze_results(self, results: Dict[str, Any]):
        """分析测试结果"""
        summary = results["test_summary"]
        
        print("\n" + "="*80)
        print("🎯 Worker并发处理能力测试结果")
        print("="*80)
        
        print(f"📊 任务统计:")
        print(f"   总任务数: {summary['total_tasks']}")
        print(f"   已完成: {summary['completed_tasks']}")
        print(f"   已失败: {summary['failed_tasks']}")
        print(f"   超时未完成: {summary['timeout_tasks']}")
        print(f"   成功率: {summary['success_rate']:.2f}%")
        
        print(f"\n⚡ 性能指标:")
        print(f"   最大并发处理数: {summary['max_concurrent_processing']}")
        print(f"   总测试时间: {summary['total_time_seconds']:.0f} 秒")
        
        if summary['completed_tasks'] > 0:
            avg_time_per_task = summary['total_time_seconds'] / summary['completed_tasks']
            print(f"   平均每任务时间: {avg_time_per_task:.1f} 秒")
            
            throughput = summary['completed_tasks'] / (summary['total_time_seconds'] / 60)
            print(f"   处理吞吐量: {throughput:.2f} 任务/分钟")
        
        # 分析并发处理历史
        processing_history = results["processing_count_history"]
        if processing_history:
            processing_counts = [h["processing"] for h in processing_history]
            avg_concurrent = sum(processing_counts) / len(processing_counts)
            print(f"   平均并发处理数: {avg_concurrent:.2f}")
        
        print("="*80)
        
        # 显示失败任务详情
        if summary['failed_tasks'] > 0:
            print(f"\n❌ 失败任务详情:")
            for task_id in results['failed_task_ids'][:5]:  # 只显示前5个
                print(f"   - {task_id}")
        
        # 显示超时任务详情
        if summary['timeout_tasks'] > 0:
            print(f"\n⏰ 超时任务详情:")
            for task_id in results['timeout_task_ids'][:5]:  # 只显示前5个
                print(f"   - {task_id}")
    
    def export_results(self, results: Dict[str, Any], filename: Optional[str] = None):
        """导出测试结果"""
        if filename is None:
            filename = f"worker_concurrency_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📁 测试结果已导出到: {filename}")
            
        except Exception as e:
            logger.error(f"导出结果失败: {e}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Worker并发处理能力测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    python test_worker_concurrency.py --count 8 --timeout 5     # 8个任务，监控5分钟
    python test_worker_concurrency.py --count 16 --quick        # 16个任务，快速模式
    python test_worker_concurrency.py --count 12 --timeout 10   # 12个任务，监控10分钟
        """
    )
    
    parser.add_argument(
        "--count", 
        type=int, 
        default=8,
        help="提交的任务数量 (默认: 8)"
    )
    
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=10,
        help="监控超时时间（分钟） (默认: 10)"
    )
    
    parser.add_argument(
        "--quick", 
        action="store_true", 
        help="快速模式，使用会快速失败的任务"
    )
    
    parser.add_argument(
        "--url", 
        default="http://api:8000",
        help="API基础URL (默认: http://api:8000)"
    )
    
    parser.add_argument(
        "--export", 
        action="store_true", 
        help="导出测试结果到JSON文件"
    )
    
    args = parser.parse_args()
    
    tester = WorkerConcurrencyTester(args.url)
    
    try:
        await tester.initialize()
        
        logger.info(f"🚀 开始Worker并发测试")
        logger.info(f"📋 任务数量: {args.count}")
        logger.info(f"⏰ 监控时间: {args.timeout} 分钟")
        logger.info(f"🏃 快速模式: {'是' if args.quick else '否'}")
        
        # 提交任务
        task_ids = await tester.submit_batch_tasks(args.count, args.quick)
        
        if not task_ids:
            logger.error("❌ 没有成功提交任何任务")
            return
        
        # 监控任务执行
        results = await tester.monitor_tasks(task_ids, args.timeout)
        
        # 分析结果
        tester.analyze_results(results)
        
        # 导出结果
        if args.export:
            tester.export_results(results)
        
    except Exception as e:
        logger.error(f"测试执行失败: {e}")
        sys.exit(1)
    
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
