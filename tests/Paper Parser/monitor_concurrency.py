#!/usr/bin/env python3
"""
并发监控脚本

监控Celery worker状态、Redis队列长度、MongoDB连接状态等关键指标
用于实时了解系统并发处理能力和瓶颈。

使用方法:
    python monitor_concurrency.py --interval 10    # 每10秒监控一次
    python monitor_concurrency.py --once           # 只监控一次
    python monitor_concurrency.py --export         # 导出监控数据到文件
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

import redis
from celery import Celery
from motor.motor_asyncio import AsyncIOMotorClient

# 添加项目路径
sys.path.insert(0, '/app')

from literature_parser_backend.settings import Settings
from loguru import logger


class ConcurrencyMonitor:
    """并发监控器"""
    
    def __init__(self):
        self.settings = Settings()
        self.redis_client = None
        self.mongo_client = None
        self.celery_app = None
        self.monitoring_data = []
    
    async def initialize(self):
        """初始化连接"""
        try:
            # Redis连接
            self.redis_client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password if self.settings.redis_password else None,
                decode_responses=True
            )
            
            # MongoDB连接
            self.mongo_client = AsyncIOMotorClient(str(self.settings.db_url))
            
            # Celery连接
            self.celery_app = Celery(
                "literature_parser_worker",
                broker=self.settings.celery_broker_url_computed,
                backend=self.settings.celery_result_backend_computed,
            )
            
            logger.info("✅ 监控器初始化成功")
            
        except Exception as e:
            logger.error(f"❌ 监控器初始化失败: {e}")
            raise
    
    async def get_redis_stats(self) -> Dict[str, Any]:
        """获取Redis统计信息"""
        try:
            info = self.redis_client.info()
            
            # 获取队列长度
            queue_length = self.redis_client.llen("celery")  # 默认队列
            literature_queue_length = self.redis_client.llen("literature")  # 文献队列
            
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "used_memory_peak_human": info.get("used_memory_peak_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
                "queue_length": queue_length,
                "literature_queue_length": literature_queue_length,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
            }
        except Exception as e:
            logger.error(f"获取Redis统计失败: {e}")
            return {"error": str(e)}
    
    async def get_celery_stats(self) -> Dict[str, Any]:
        """获取Celery统计信息"""
        try:
            inspect = self.celery_app.control.inspect()
            
            # 获取活跃任务
            active_tasks = inspect.active()
            
            # 获取worker统计
            stats = inspect.stats()
            
            # 获取注册任务
            registered_tasks = inspect.registered()
            
            # 计算总体统计
            total_active_tasks = 0
            total_workers = 0
            worker_details = {}
            
            if active_tasks:
                for worker, tasks in active_tasks.items():
                    total_active_tasks += len(tasks)
                    total_workers += 1
                    worker_details[worker] = {
                        "active_tasks": len(tasks),
                        "task_details": [
                            {
                                "id": task.get("id", "unknown"),
                                "name": task.get("name", "unknown"),
                                "time_start": task.get("time_start", 0),
                            }
                            for task in tasks
                        ]
                    }
            
            # 获取worker负载
            worker_load = {}
            if stats:
                for worker, stat in stats.items():
                    pool = stat.get("pool", {})
                    worker_load[worker] = {
                        "processes": pool.get("processes", []),
                        "max_concurrency": pool.get("max-concurrency", 0),
                        "max_memory_per_child": pool.get("max-memory-per-child", 0),
                    }
            
            return {
                "total_workers": total_workers,
                "total_active_tasks": total_active_tasks,
                "worker_details": worker_details,
                "worker_load": worker_load,
                "registered_tasks_count": len(registered_tasks) if registered_tasks else 0,
            }
            
        except Exception as e:
            logger.error(f"获取Celery统计失败: {e}")
            return {"error": str(e)}
    
    async def get_mongodb_stats(self) -> Dict[str, Any]:
        """获取MongoDB统计信息"""
        try:
            db = self.mongo_client.get_database()
            
            # 数据库统计
            db_stats = await db.command("dbStats")
            
            # 集合统计
            collection = db.literatures
            collection_stats = await db.command("collStats", "literatures")
            
            # 连接统计
            server_status = await db.command("serverStatus")
            connections = server_status.get("connections", {})
            
            # 文献统计
            total_literature = await collection.count_documents({})
            processing_literature = await collection.count_documents({
                "task_info.status": {"$in": ["pending", "processing", "in_progress"]}
            })
            failed_literature = await collection.count_documents({
                "task_info.status": "failed"
            })
            completed_literature = await collection.count_documents({
                "task_info.status": "completed"
            })
            
            return {
                "database_size_mb": round(db_stats.get("dataSize", 0) / 1024 / 1024, 2),
                "storage_size_mb": round(db_stats.get("storageSize", 0) / 1024 / 1024, 2),
                "index_size_mb": round(db_stats.get("indexSize", 0) / 1024 / 1024, 2),
                "collections": db_stats.get("collections", 0),
                "objects": db_stats.get("objects", 0),
                "current_connections": connections.get("current", 0),
                "available_connections": connections.get("available", 0),
                "total_created_connections": connections.get("totalCreated", 0),
                "literature_stats": {
                    "total": total_literature,
                    "processing": processing_literature,
                    "failed": failed_literature,
                    "completed": completed_literature,
                    "success_rate": round(completed_literature / max(total_literature, 1) * 100, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"获取MongoDB统计失败: {e}")
            return {"error": str(e)}
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """收集所有监控指标"""
        timestamp = datetime.now()
        
        logger.info("📊 正在收集监控指标...")
        
        # 并行收集所有指标
        redis_stats, celery_stats, mongodb_stats = await asyncio.gather(
            self.get_redis_stats(),
            self.get_celery_stats(),
            self.get_mongodb_stats(),
            return_exceptions=True
        )
        
        metrics = {
            "timestamp": timestamp.isoformat(),
            "redis": redis_stats if not isinstance(redis_stats, Exception) else {"error": str(redis_stats)},
            "celery": celery_stats if not isinstance(celery_stats, Exception) else {"error": str(celery_stats)},
            "mongodb": mongodb_stats if not isinstance(mongodb_stats, Exception) else {"error": str(mongodb_stats)},
        }
        
        return metrics
    
    def display_metrics(self, metrics: Dict[str, Any]):
        """显示监控指标"""
        print("\n" + "="*80)
        print(f"🕐 监控时间: {metrics['timestamp']}")
        print("="*80)
        
        # Redis指标
        redis_data = metrics.get("redis", {})
        if "error" not in redis_data:
            print(f"📊 Redis状态:")
            print(f"   连接客户端: {redis_data.get('connected_clients', 0)}")
            print(f"   内存使用: {redis_data.get('used_memory_human', '0B')}")
            print(f"   队列长度: {redis_data.get('literature_queue_length', 0)}")
            print(f"   每秒操作: {redis_data.get('instantaneous_ops_per_sec', 0)}")
        else:
            print(f"❌ Redis错误: {redis_data['error']}")
        
        # Celery指标
        celery_data = metrics.get("celery", {})
        if "error" not in celery_data:
            print(f"\n🔄 Celery状态:")
            print(f"   活跃Worker: {celery_data.get('total_workers', 0)}")
            print(f"   活跃任务: {celery_data.get('total_active_tasks', 0)}")
            
            worker_details = celery_data.get("worker_details", {})
            for worker, details in worker_details.items():
                print(f"   Worker {worker}: {details['active_tasks']} 个任务")
        else:
            print(f"❌ Celery错误: {celery_data['error']}")
        
        # MongoDB指标
        mongodb_data = metrics.get("mongodb", {})
        if "error" not in mongodb_data:
            print(f"\n💾 MongoDB状态:")
            print(f"   数据库大小: {mongodb_data.get('database_size_mb', 0)} MB")
            print(f"   当前连接: {mongodb_data.get('current_connections', 0)}")
            
            lit_stats = mongodb_data.get("literature_stats", {})
            print(f"   文献总数: {lit_stats.get('total', 0)}")
            print(f"   处理中: {lit_stats.get('processing', 0)}")
            print(f"   已完成: {lit_stats.get('completed', 0)}")
            print(f"   失败: {lit_stats.get('failed', 0)}")
            print(f"   成功率: {lit_stats.get('success_rate', 0)}%")
        else:
            print(f"❌ MongoDB错误: {mongodb_data['error']}")
        
        print("="*80)
    
    async def monitor_once(self):
        """执行一次监控"""
        await self.initialize()
        metrics = await self.collect_metrics()
        self.display_metrics(metrics)
        return metrics
    
    async def monitor_continuous(self, interval: int = 10):
        """持续监控"""
        await self.initialize()
        
        logger.info(f"🚀 开始持续监控，间隔 {interval} 秒")
        logger.info("按 Ctrl+C 停止监控")
        
        try:
            while True:
                metrics = await self.collect_metrics()
                self.display_metrics(metrics)
                self.monitoring_data.append(metrics)
                
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 监控已停止")
    
    def export_data(self, filename: Optional[str] = None):
        """导出监控数据"""
        if not self.monitoring_data:
            logger.warning("没有监控数据可导出")
            return
        
        if filename is None:
            filename = f"concurrency_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.monitoring_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📁 监控数据已导出到: {filename}")
            
        except Exception as e:
            logger.error(f"导出数据失败: {e}")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="并发监控脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    python monitor_concurrency.py --once           # 监控一次
    python monitor_concurrency.py --interval 10    # 每10秒监控一次
    python monitor_concurrency.py --export         # 导出数据
        """
    )
    
    parser.add_argument(
        "--once", 
        action="store_true", 
        help="只监控一次"
    )
    
    parser.add_argument(
        "--interval", 
        type=int, 
        default=10,
        help="持续监控的间隔秒数 (默认: 10)"
    )
    
    parser.add_argument(
        "--export", 
        action="store_true", 
        help="导出监控数据到JSON文件"
    )
    
    args = parser.parse_args()
    
    monitor = ConcurrencyMonitor()
    
    try:
        if args.once:
            await monitor.monitor_once()
        elif args.export:
            # 先监控一次收集数据
            await monitor.monitor_once()
            monitor.export_data()
        else:
            await monitor.monitor_continuous(args.interval)
            
    except Exception as e:
        logger.error(f"监控执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
