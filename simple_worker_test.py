#!/usr/bin/env python3
"""
简化的Worker并发测试

直接提交任务，然后通过监控脚本观察Worker的并发处理情况。
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from loguru import logger


async def submit_tasks(count: int, base_url: str = "http://api:8000"):
    """提交指定数量的测试任务"""
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        logger.info(f"🚀 开始提交 {count} 个测试任务...")
        
        tasks = []
        for i in range(count):
            # 使用会快速失败的URL来测试并发能力
            task_data = {
                "url": f"https://httpbin.org/status/404?test={i}",
                "title": f"Worker Concurrency Test {i}",
                "authors": [f"Test Author {i}"]
            }
            
            task = asyncio.create_task(
                submit_single_task(session, task_data, i),
                name=f"submit_{i}"
            )
            tasks.append(task)
        
        # 等待所有任务提交完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_submissions = 0
        task_ids = []
        
        for i, result in enumerate(results):
            if isinstance(result, str):  # task_id
                successful_submissions += 1
                task_ids.append(result)
                logger.info(f"✅ 任务 {i} 提交成功: {result}")
            else:
                logger.error(f"❌ 任务 {i} 提交失败: {result}")
        
        logger.info(f"📊 提交完成: {successful_submissions}/{count} 个任务成功")
        return task_ids


async def submit_single_task(session, task_data, index):
    """提交单个任务"""
    url = "http://api:8000/api/literature/"
    
    try:
        async with session.post(url, json=task_data) as response:
            if response.status in [200, 201, 202]:
                response_data = await response.json()
                return response_data.get("task_id")
            else:
                error_text = await response.text()
                return f"HTTP {response.status}: {error_text}"
    except Exception as e:
        return f"Exception: {e}"


def print_instructions():
    """打印测试说明"""
    print("\n" + "="*80)
    print("🎯 Worker并发测试说明")
    print("="*80)
    print("1. 任务已提交到队列中")
    print("2. 请在另一个终端运行以下命令来监控Worker状态:")
    print("   sudo docker exec -it paper_paser_1-worker-1 python3 /app/monitor_concurrency.py --interval 5")
    print("3. 观察以下指标:")
    print("   - 活跃任务数量 (应该能看到多个任务同时处理)")
    print("   - 队列长度变化")
    print("   - 处理速度")
    print("4. 按 Ctrl+C 停止监控")
    print("="*80)


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="简化的Worker并发测试")
    parser.add_argument("--count", type=int, default=12, help="提交的任务数量")
    parser.add_argument("--url", default="http://api:8000", help="API基础URL")
    
    args = parser.parse_args()
    
    logger.info(f"🚀 开始Worker并发测试")
    logger.info(f"📋 任务数量: {args.count}")
    logger.info(f"🌐 API地址: {args.url}")
    logger.info(f"⏰ 开始时间: {datetime.now()}")
    
    # 提交任务
    start_time = time.time()
    task_ids = await submit_tasks(args.count, args.url)
    end_time = time.time()
    
    logger.info(f"✅ 任务提交完成，耗时: {end_time - start_time:.2f}s")
    logger.info(f"📊 成功提交: {len(task_ids)} 个任务")
    
    if task_ids:
        print_instructions()
        
        # 显示任务ID
        print(f"\n📝 提交的任务ID:")
        for i, task_id in enumerate(task_ids[:10]):  # 只显示前10个
            print(f"  {i+1}. {task_id}")
        if len(task_ids) > 10:
            print(f"  ... 还有 {len(task_ids) - 10} 个任务")
    else:
        logger.error("❌ 没有成功提交任何任务")


if __name__ == "__main__":
    asyncio.run(main())
