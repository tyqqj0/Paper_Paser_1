#!/usr/bin/env python3
"""
简化的系统测试脚本
"""

import asyncio
import logging
import os
import time

import httpx

# Give services a moment to start up
# time.sleep(5) # No need to sleep when running inside the same network

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8088/api/v1")
DOI = "10.1109/5.771073"
ARXIV_ID = "1706.03762"

logger = logging.getLogger(__name__)


async def test_literature_parser() -> bool:
    """测试文献解析器系统"""
    print("🚀 Literature Parser 系统测试")
    print("=" * 50)

    # 使用一个新的测试URL
    test_url = "http://arxiv.org/abs/2205.14217"  # 已知存在的ArXiv论文

    async with httpx.AsyncClient(timeout=300.0) as client:
        # 1. API健康检查
        try:
            response = await client.get("http://127.0.0.1:8088/api/health")
            if response.status_code == 200:
                logger.info("✅ API服务正常")
            else:
                logger.error(f"❌ API服务异常: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ API连接失败: {e}")
            return False

        # 2. 提交文献处理任务
        try:
            response = await client.post(
                "http://127.0.0.1:8088/api/literature",
                json={"url": "http://arxiv.org/abs/2205.14217"},
                timeout=30,
            )
            if response.status_code == 202:
                task_info = response.json()
                task_id = task_info.get("task_id")
                logger.info(f"✅ 任务提交成功，任务ID: {task_id}")
            else:
                logger.error(
                    f"❌ 任务提交失败: {response.status_code} - {response.text}",
                )
                return False
        except Exception as e:
            logger.error(f"❌ 任务提交异常: {e}")
            return False

        # 3. 监控任务进度
        literature_id = None
        max_wait_time = 120  # 最多等待2分钟
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = await client.get(f"http://127.0.0.1:8088/api/task/{task_id}")
                task_data = response.json()

                status = task_data.get("status", "unknown")
                logger.debug(f"任务状态: {status}")

                if status == "success":
                    literature_id = task_data.get("literature_id")
                    if literature_id:
                        logger.info(f"🎉 任务完成！文献ID: {literature_id}")
                        break
                    else:
                        logger.error("❌ 任务完成但没有返回文献ID")
                        return False
                elif status == "failure":
                    error_msg = task_data.get("result", {}).get("error", "未知错误")
                    logger.error(f"❌ 任务失败: {error_msg}")
                    return False

                await asyncio.sleep(3)

            except Exception as e:
                logger.warning(f"❌ 任务状态查询异常: {e}")
                await asyncio.sleep(3)
                continue
        else:
            logger.error(f"⏰ 任务超时 (>{max_wait_time}秒)")
            return False

        # 4. 检查文献信息
        if not literature_id:
            return False

        try:
            response = await client.get(
                f"http://127.0.0.1:8088/api/literature/{literature_id}",
            )
            if response.status_code == 200:
                lit_data = response.json()
                print("\n✅ 文献信息获取成功:")
                print(f"   - 标题: {lit_data.get('title', 'N/A')}")
                print(f"   - 作者: {len(lit_data.get('authors', []))} 位")
                print(f"   - 年份: {lit_data.get('year', 'N/A')}")
                print(f"   - DOI: {lit_data.get('doi', 'N/A')}")
                print(f"   - 参考文献: {len(lit_data.get('references', []))} 篇")
            else:
                logger.error(f"❌ 文献信息获取失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 获取文献信息异常: {e}")
            return False

        print("=" * 50)
        print("✅ 系统测试全部通过！")
        return True


if __name__ == "__main__":
    success = asyncio.run(test_literature_parser())
    if not success:
        print("\n❌ 系统测试失败")
        exit(1)
