#!/usr/bin/env python3
"""
清理Redis队列中的任务

清理Celery队列中积压的任务，特别是测试任务。

使用方法:
    python clear_queue.py --dry-run     # 只显示要清理的任务，不实际清理
    python clear_queue.py --confirm     # 确认清理队列
    python clear_queue.py --queue literature --confirm  # 清理指定队列
"""

import argparse
import json
import sys
from datetime import datetime

import redis
from loguru import logger

# 添加项目路径
sys.path.insert(0, '/app')

from literature_parser_backend.settings import Settings


class QueueCleaner:
    """队列清理器"""
    
    def __init__(self):
        self.settings = Settings()
        self.redis_client = None
        self.cleared_count = 0
    
    def initialize(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password if self.settings.redis_password else None,
                decode_responses=True
            )
            
            # 测试连接
            self.redis_client.ping()
            logger.info("✅ Redis连接成功")
            
        except Exception as e:
            logger.error(f"❌ Redis连接失败: {e}")
            raise
    
    def get_queue_info(self, queue_name: str = "literature") -> dict:
        """获取队列信息"""
        try:
            queue_length = self.redis_client.llen(queue_name)
            
            # 获取队列中的前10个任务作为样本
            sample_tasks = []
            if queue_length > 0:
                raw_tasks = self.redis_client.lrange(queue_name, 0, 9)  # 获取前10个
                for raw_task in raw_tasks:
                    try:
                        task_data = json.loads(raw_task)
                        sample_tasks.append({
                            "task_id": task_data.get("id", "unknown"),
                            "task_name": task_data.get("task", "unknown"),
                            "args": task_data.get("args", []),
                            "kwargs": task_data.get("kwargs", {}),
                        })
                    except json.JSONDecodeError:
                        sample_tasks.append({"raw": raw_task[:100] + "..." if len(raw_task) > 100 else raw_task})
            
            return {
                "queue_name": queue_name,
                "length": queue_length,
                "sample_tasks": sample_tasks
            }
            
        except Exception as e:
            logger.error(f"获取队列信息失败: {e}")
            return {"error": str(e)}
    
    def display_queue_info(self, queue_info: dict):
        """显示队列信息"""
        if "error" in queue_info:
            logger.error(f"❌ 队列信息获取失败: {queue_info['error']}")
            return
        
        queue_name = queue_info["queue_name"]
        length = queue_info["length"]
        sample_tasks = queue_info["sample_tasks"]
        
        print(f"\n📋 队列信息: {queue_name}")
        print("="*60)
        print(f"队列长度: {length} 个任务")
        
        if length == 0:
            print("✅ 队列为空")
            return
        
        print(f"\n📝 任务样本 (前{len(sample_tasks)}个):")
        for i, task in enumerate(sample_tasks, 1):
            if "raw" in task:
                print(f"  {i}. [原始数据] {task['raw']}")
            else:
                task_id = task.get("task_id", "unknown")
                task_name = task.get("task_name", "unknown")
                print(f"  {i}. ID: {task_id}")
                print(f"     任务: {task_name}")
                
                # 显示参数信息
                args = task.get("args", [])
                kwargs = task.get("kwargs", {})
                if args:
                    print(f"     参数: {args}")
                if kwargs:
                    # 只显示关键信息
                    key_info = {}
                    for key in ["url", "title", "literature_id"]:
                        if key in kwargs:
                            value = kwargs[key]
                            if isinstance(value, str) and len(value) > 50:
                                key_info[key] = value[:50] + "..."
                            else:
                                key_info[key] = value
                    if key_info:
                        print(f"     关键词: {key_info}")
        
        print("="*60)
    
    def clear_queue(self, queue_name: str = "literature", dry_run: bool = True) -> int:
        """清理队列"""
        try:
            queue_length = self.redis_client.llen(queue_name)
            
            if queue_length == 0:
                logger.info(f"✅ 队列 {queue_name} 已经为空")
                return 0
            
            if dry_run:
                logger.info(f"🔍 [干运行模式] 将要清理队列 {queue_name} 中的 {queue_length} 个任务")
                logger.info("💡 使用 --confirm 参数来实际执行清理操作")
                return queue_length
            
            logger.info(f"🗑️  开始清理队列 {queue_name} 中的 {queue_length} 个任务...")
            
            # 删除整个队列
            deleted_count = self.redis_client.delete(queue_name)
            
            if deleted_count > 0:
                logger.info(f"✅ 成功清理队列 {queue_name}，删除了 {queue_length} 个任务")
                self.cleared_count = queue_length
            else:
                logger.warning(f"⚠️  队列 {queue_name} 可能已经为空")
                self.cleared_count = 0
            
            return self.cleared_count
            
        except Exception as e:
            logger.error(f"❌ 清理队列失败: {e}")
            return 0
    
    def clear_all_celery_queues(self, dry_run: bool = True):
        """清理所有Celery相关队列"""
        celery_queues = [
            "celery",           # 默认队列
            "literature",       # 文献处理队列
            "high_priority",    # 高优先级队列（如果有）
            "low_priority",     # 低优先级队列（如果有）
        ]
        
        total_cleared = 0
        
        for queue_name in celery_queues:
            logger.info(f"\n🔍 检查队列: {queue_name}")
            queue_info = self.get_queue_info(queue_name)
            
            if "error" not in queue_info and queue_info["length"] > 0:
                self.display_queue_info(queue_info)
                cleared = self.clear_queue(queue_name, dry_run)
                total_cleared += cleared
            else:
                logger.info(f"✅ 队列 {queue_name} 为空或不存在")
        
        return total_cleared
    
    def cleanup(self, queue_name: str = None, dry_run: bool = True):
        """执行清理操作"""
        logger.info("🚀 开始队列清理操作...")
        logger.info(f"📅 执行时间: {datetime.now()}")
        logger.info(f"🔧 模式: {'干运行' if dry_run else '实际清理'}")
        
        try:
            self.initialize()
            
            if queue_name:
                # 清理指定队列
                logger.info(f"🎯 清理指定队列: {queue_name}")
                queue_info = self.get_queue_info(queue_name)
                self.display_queue_info(queue_info)
                
                if "error" not in queue_info and queue_info["length"] > 0:
                    self.clear_queue(queue_name, dry_run)
                else:
                    logger.info(f"✅ 队列 {queue_name} 为空或不存在")
            else:
                # 清理所有队列
                logger.info("🎯 清理所有Celery队列")
                self.clear_all_celery_queues(dry_run)
            
            logger.info("🎉 队列清理操作完成!")
            
        except Exception as e:
            logger.error(f"❌ 清理操作失败: {e}")
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="清理Redis队列中的任务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    python clear_queue.py --dry-run                    # 查看要清理的任务
    python clear_queue.py --confirm                    # 清理所有队列
    python clear_queue.py --queue literature --confirm # 清理指定队列
        """
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        default=True,
        help="干运行模式，只显示要清理的任务，不实际清理 (默认)"
    )
    
    parser.add_argument(
        "--confirm", 
        action="store_true", 
        help="确认清理模式，实际执行清理操作"
    )
    
    parser.add_argument(
        "--queue", 
        help="指定要清理的队列名称，不指定则清理所有队列"
    )
    
    args = parser.parse_args()
    
    # 确定运行模式
    dry_run = not args.confirm
    
    if not dry_run:
        # 确认清理前的警告
        logger.warning("⚠️  您即将清理Redis队列中的任务!")
        logger.warning("⚠️  这将删除所有等待处理的任务，此操作不可逆!")
        
        confirm = input("\n请输入 'YES' 来确认清理操作: ")
        if confirm != "YES":
            logger.info("❌ 操作已取消")
            return
    
    # 执行清理
    cleaner = QueueCleaner()
    cleaner.cleanup(queue_name=args.queue, dry_run=dry_run)


if __name__ == "__main__":
    main()
