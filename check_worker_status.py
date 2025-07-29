#!/usr/bin/env python3
"""
检查Celery Worker的详细状态

检查Worker的实际配置、进程数、并发设置等详细信息。
"""

import sys
import os
from celery import Celery
from loguru import logger

# 添加项目路径
sys.path.insert(0, '/app')

from literature_parser_backend.settings import Settings
from literature_parser_backend.worker.celery_app import celery_app


def check_worker_status():
    """检查Worker状态"""
    logger.info("🔍 检查Celery Worker状态...")
    
    try:
        # 获取设置
        settings = Settings()
        
        print("="*80)
        print("📋 Celery配置信息")
        print("="*80)
        print(f"Broker URL: {settings.celery_broker_url_computed}")
        print(f"Result Backend: {settings.celery_result_backend_computed}")
        print(f"Task Time Limit: {settings.celery_task_time_limit}s")
        print(f"Task Soft Time Limit: {settings.celery_task_soft_time_limit}s")
        print(f"Worker Prefetch Multiplier: {settings.celery_worker_prefetch_multiplier}")
        
        # 检查Celery应用配置
        print(f"\n📋 Celery应用配置")
        print("="*80)
        print(f"App Name: {celery_app.main}")
        print(f"Broker: {celery_app.conf.broker_url}")
        print(f"Backend: {celery_app.conf.result_backend}")
        
        # 获取Worker信息
        inspect = celery_app.control.inspect()
        
        print(f"\n🔍 Worker检查")
        print("="*80)
        
        # 检查活跃的Workers
        try:
            active_workers = inspect.active()
            if active_workers:
                print(f"活跃Workers数量: {len(active_workers)}")
                for worker_name, tasks in active_workers.items():
                    print(f"  Worker: {worker_name}")
                    print(f"    活跃任务数: {len(tasks)}")
                    for task in tasks[:3]:  # 只显示前3个任务
                        print(f"      - {task.get('name', 'unknown')} ({task.get('id', 'unknown')[:8]}...)")
            else:
                print("❌ 没有发现活跃的Workers")
        except Exception as e:
            print(f"❌ 获取活跃Workers失败: {e}")
        
        # 检查Worker统计信息
        try:
            stats = inspect.stats()
            if stats:
                print(f"\n📊 Worker统计信息")
                print("-"*60)
                for worker_name, stat in stats.items():
                    print(f"Worker: {worker_name}")
                    pool_info = stat.get('pool', {})
                    print(f"  进程池信息:")
                    print(f"    最大并发数: {pool_info.get('max-concurrency', 'unknown')}")
                    print(f"    进程数: {len(pool_info.get('processes', []))}")
                    print(f"    进程列表: {pool_info.get('processes', [])}")
                    
                    # 其他统计信息
                    print(f"  总任务数: {stat.get('total', {})}")
                    print(f"  运行时间: {stat.get('rusage', {}).get('utime', 'unknown')}s")
            else:
                print("❌ 没有获取到Worker统计信息")
        except Exception as e:
            print(f"❌ 获取Worker统计失败: {e}")
        
        # 检查注册的任务
        try:
            registered = inspect.registered()
            if registered:
                print(f"\n📝 注册的任务")
                print("-"*60)
                for worker_name, tasks in registered.items():
                    print(f"Worker {worker_name}: {len(tasks)} 个任务")
                    for task in tasks[:5]:  # 只显示前5个
                        print(f"  - {task}")
            else:
                print("❌ 没有获取到注册任务信息")
        except Exception as e:
            print(f"❌ 获取注册任务失败: {e}")
        
        # 检查队列信息
        try:
            reserved = inspect.reserved()
            if reserved:
                print(f"\n📦 预留任务")
                print("-"*60)
                for worker_name, tasks in reserved.items():
                    print(f"Worker {worker_name}: {len(tasks)} 个预留任务")
            else:
                print("✅ 没有预留任务")
        except Exception as e:
            print(f"❌ 获取预留任务失败: {e}")
        
        print("="*80)
        
    except Exception as e:
        logger.error(f"❌ 检查Worker状态失败: {e}")


def check_process_info():
    """检查进程信息"""
    logger.info("🔍 检查进程信息...")
    
    try:
        import multiprocessing
        print(f"\n🖥️  系统信息")
        print("="*80)
        print(f"CPU核心数: {multiprocessing.cpu_count()}")
        print(f"当前进程ID: {os.getpid()}")
        print(f"父进程ID: {os.getppid()}")
        
        # 尝试获取环境变量
        print(f"\n🌍 环境变量")
        print("-"*60)
        celery_vars = {k: v for k, v in os.environ.items() if 'CELERY' in k.upper()}
        if celery_vars:
            for key, value in celery_vars.items():
                print(f"{key}: {value}")
        else:
            print("没有找到Celery相关环境变量")
        
        # 检查Python多进程设置
        print(f"\n🐍 Python多进程设置")
        print("-"*60)
        print(f"multiprocessing.get_start_method(): {multiprocessing.get_start_method()}")
        
    except Exception as e:
        logger.error(f"❌ 检查进程信息失败: {e}")


if __name__ == "__main__":
    check_worker_status()
    check_process_info()
