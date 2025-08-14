#!/usr/bin/env python3
"""
论文重复添加测试脚本

测试同一篇论文添加两次的情况，验证查重机制是否正常工作。
"""

import asyncio
import json
import time
import requests
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE_URL = "http://localhost:8000/api"


async def clear_database() -> None:
    """清空数据库，方便测试"""
    logger.info("🗑️ 清空数据库...")
    try:
        response = requests.delete(f"{API_BASE_URL}/test/clear-database")
        # logger.info(f"   ✅ 数据库清空完成: {response.json()}")
    except Exception as e:
        logger.error(f"   ❌ 数据库清空失败: {e}")
        raise


async def create_literature(url: str, description: str) -> Dict[str, Any]:
    """创建文献解析任务"""
    logger.info(f"🧪 测试: {description}")
    logger.info(f"   URL: {url}")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/literature",
            json={"url": url}
        )
        response_data = response.json()
        logger.info(f"   📨 响应: {response_data}")
        
        task_id = response_data.get("task_id")
        if not task_id:
            logger.error(f"   ❌ 任务ID未找到: {response_data}")
            return response_data
            
        logger.info(f"   🆔 任务ID: {task_id}")
        return response_data
    except Exception as e:
        logger.error(f"   ❌ 请求失败: {e}")
        return {"error": str(e)}


async def wait_for_processing(task_id: str, description: str, wait_time: int = 10) -> Dict[str, Any]:
    """等待任务处理完成"""
    logger.info(f"   ⏳ 等待{wait_time}秒让任务完成...")
    await asyncio.sleep(wait_time)
    
    # 查看日志
    logger.info(f"   📋 检查worker日志:")
    
    # 查询文献列表
    logger.info(f"   📚 查看数据库中的文献:")
    try:
        response = requests.get(f"{API_BASE_URL}/literature")
        literature_list = response.json()
        for lit in literature_list[:5]:  # 只显示前5条
            logger.info(f"       - {lit.get('id')}: {lit.get('title')}")
        return {"literature_list": literature_list}
    except Exception as e:
        logger.error(f"   ⚠️ 查询文献列表失败: {e}")
        return {"error": str(e)}


async def run_test() -> None:
    """运行测试"""
    print("\n🎯 论文重复添加测试")
    print("="*50)
    
    # 清空数据库
    await clear_database()
    
    # 测试 - 先添加论文
    test_description = "首次添加 Attention is All You Need 论文"
    response1 = await create_literature(
        "https://arxiv.org/abs/1706.03762", 
        test_description
    )
    task_id1 = response1.get("task_id")
    if not task_id1:
        logger.error("   ❌ 测试失败：无法获取任务ID")
        return
    
    # 等待处理完成
    await wait_for_processing(task_id1, test_description)
    
    # 添加与之前相同的论文（不同URL格式）
    test_description2 = "重复添加 Attention is All You Need 论文（不同URL）"
    response2 = await create_literature(
        "https://arxiv.org/pdf/1706.03762.pdf", 
        test_description2
    )
    task_id2 = response2.get("task_id")
    if not task_id2:
        logger.error("   ❌ 测试失败：无法获取第二个任务ID")
        return
    
    # 等待处理完成
    result = await wait_for_processing(task_id2, test_description2)
    
    # 检查结果
    literature_list = result.get("literature_list", [])
    
    # 计算有多少个标题包含 "Attention is All You Need"
    attention_papers = [
        paper for paper in literature_list 
        if paper.get("title") and "attention is all you need" in paper.get("title", "").lower()
    ]
    
    # 验证结果
    if len(attention_papers) == 1:
        logger.info(f"\n✅ 测试通过！查重成功，数据库中只有一个 'Attention is All You Need' 论文记录")
    else:
        logger.error(f"\n❌ 测试失败！预期只有一条记录，但找到了 {len(attention_papers)} 条")
        for paper in attention_papers:
            logger.error(f"   - {paper.get('id')}: {paper.get('title')}")


if __name__ == "__main__":
    asyncio.run(run_test())