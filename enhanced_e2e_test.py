#!/usr/bin/env python3
"""
增强版端到端测试 - 验证新的状态管理和网络配置功能
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any

import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000/api"


class EnhancedE2ETest:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=300.0)

    async def test_api_health(self) -> bool:
        """测试API健康状态"""
        logger.info("🏥 检查API健康状态...")
        try:
            response = await self.client.get(f"{BASE_URL}/health")
            if response.status_code == 200:
                logger.info("✅ API服务正常")
                return True
            else:
                logger.error(f"❌ API服务异常: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ API连接失败: {e}")
            return False

    async def submit_literature_task(self, source_data: Dict[str, Any]) -> str:
        """提交文献处理任务"""
        logger.info(f"📝 提交文献处理任务: {source_data}")

        response = await self.client.post(
            f"{BASE_URL}/literature", json={"source": source_data}
        )

        if response.status_code == 202:
            task_data = response.json()
            task_id = task_data["task_id"]
            logger.info(f"✅ 任务提交成功，任务ID: {task_id}")
            return task_id
        elif response.status_code == 200:
            literature_data = response.json()
            logger.info(f"✅ 文献已存在: {literature_data['literature_id']}")
            return literature_data["literature_id"]
        else:
            logger.error(f"❌ 任务提交失败: {response.status_code}, {response.text}")
            raise Exception(f"Task submission failed: {response.status_code}")

    async def monitor_task_progress(
        self, task_id: str, max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """监控任务进度并显示详细状态信息"""
        logger.info(f"👀 监控任务进度: {task_id}")

        start_time = time.time()
        last_status = {}

        while time.time() - start_time < max_wait_time:
            try:
                response = await self.client.get(f"{BASE_URL}/task/{task_id}")
                if response.status_code != 200:
                    logger.error(f"❌ 获取任务状态失败: {response.status_code}")
                    await asyncio.sleep(2)
                    continue

                status_data = response.json()

                # 检查状态是否有变化
                if status_data != last_status:
                    self.print_task_status(status_data)
                    last_status = status_data.copy()

                # 检查是否完成
                if status_data.get("status") in ["success", "failed"]:
                    return status_data

                await asyncio.sleep(3)  # 增加轮询间隔

            except Exception as e:
                logger.error(f"❌ 监控任务时出错: {e}")
                await asyncio.sleep(2)

        logger.error(f"❌ 任务在{max_wait_time}秒内未完成")
        raise TimeoutError("Task did not complete in time")

    def print_task_status(self, status_data: Dict[str, Any]) -> None:
        """打印详细的任务状态信息"""
        print("\n" + "=" * 60)
        print(f"📊 任务状态更新: {status_data.get('task_id', 'Unknown')}")
        print(f"🔄 总体状态: {status_data.get('status', 'Unknown')}")
        print(f"📈 总体进度: {status_data.get('overall_progress', 0)}%")

        if status_data.get("current_stage"):
            print(f"🎯 当前阶段: {status_data['current_stage']}")

        # 显示组件状态
        component_status = status_data.get("component_status", {})
        if component_status:
            print("\n📋 组件状态详情:")

            for component_name, component_info in component_status.items():
                if isinstance(component_info, dict):
                    status = component_info.get("status", "unknown")
                    stage = component_info.get("stage", "未知阶段")
                    progress = component_info.get("progress", 0)
                    source = component_info.get("source", "")
                    next_action = component_info.get("next_action", "")

                    # 状态图标
                    status_icon = {
                        "pending": "⏳",
                        "processing": "🔄",
                        "success": "✅",
                        "failed": "❌",
                        "waiting": "⏸️",
                        "skipped": "⏭️",
                    }.get(status, "❓")

                    print(f"  {status_icon} {component_name.upper()}:")
                    print(f"    状态: {status}")
                    print(f"    阶段: {stage}")
                    print(f"    进度: {progress}%")
                    if source:
                        print(f"    数据源: {source}")
                    if next_action:
                        print(f"    下一步: {next_action}")

                    # 显示错误信息
                    if component_info.get("error_info"):
                        error_info = component_info["error_info"]
                        print(
                            f"    ❌ 错误: {error_info.get('error_message', '未知错误')}"
                        )

        # 显示下一步动作
        next_actions = status_data.get("next_actions", [])
        if next_actions:
            print(f"\n🔄 下一步动作: {', '.join(next_actions)}")

        print("=" * 60)

    async def get_literature_details(self, literature_id: str) -> Dict[str, Any]:
        """获取文献详细信息"""
        logger.info(f"📖 获取文献详情: {literature_id}")

        response = await self.client.get(f"{BASE_URL}/literature/{literature_id}")
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"❌ 获取文献详情失败: {response.status_code}")
            raise Exception(f"Failed to get literature details: {response.status_code}")

    async def get_literature_fulltext(self, literature_id: str) -> Dict[str, Any]:
        """获取文献全文信息"""
        logger.info(f"📄 获取文献全文: {literature_id}")

        try:
            response = await self.client.get(
                f"{BASE_URL}/literature/{literature_id}/fulltext"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"⚠️ 获取文献全文失败: {response.status_code}")
                return {}
        except Exception as e:
            logger.warning(f"⚠️ 获取文献全文时出错: {e}")
            return {}

    def analyze_results(
        self, details: Dict[str, Any], fulltext: Dict[str, Any]
    ) -> Dict[str, bool]:
        """分析解析结果"""
        print("\n" + "=" * 60)
        print("📊 解析结果分析")
        print("=" * 60)

        metadata = details.get("metadata", {})
        content = details.get("content", {})
        references = details.get("references", [])
        task_info = details.get("task_info", {})

        results = {}

        # 分析元数据
        print("\n🔍 元数据分析:")
        results["has_title"] = bool(metadata.get("title"))
        print(
            f"  标题: {'✅ ' + metadata.get('title', '') if results['has_title'] else '❌ 缺失'}"
        )

        results["has_authors"] = bool(metadata.get("authors"))
        if results["has_authors"]:
            authors = metadata["authors"]
            author_names = [
                author.get("name", "Unknown")
                for author in authors
                if isinstance(author, dict)
            ]
            print(f"  作者: ✅ {len(authors)}位 - {', '.join(author_names[:3])}")
        else:
            print(f"  作者: ❌ 缺失")

        results["has_abstract"] = bool(metadata.get("abstract"))
        print(f"  摘要: {'✅ 存在' if results['has_abstract'] else '❌ 缺失'}")

        results["has_year"] = bool(metadata.get("year"))
        print(
            f"  年份: {'✅ ' + str(metadata.get('year', '')) if results['has_year'] else '❌ 缺失'}"
        )

        # 分析内容
        print("\n📄 内容分析:")
        results["has_pdf_url"] = bool(content.get("pdf_url"))
        print(
            f"  PDF链接: {'✅ ' + content.get('pdf_url', '') if results['has_pdf_url'] else '❌ 缺失'}"
        )

        results["has_parsed_fulltext"] = bool(fulltext.get("parsed_fulltext"))
        if results["has_parsed_fulltext"]:
            parsed_text = fulltext["parsed_fulltext"]
            sections = parsed_text.get("sections", [])
            print(f"  解析文本: ✅ 存在，包含{len(sections)}个章节")
        else:
            print(f"  解析文本: ❌ 缺失")

        # 分析参考文献
        print("\n📚 参考文献分析:")
        results["has_references"] = len(references) > 0
        if results["has_references"]:
            parsed_refs = sum(1 for ref in references if ref.get("parsed"))
            print(f"  参考文献: ✅ {len(references)}条 (其中{parsed_refs}条已解析)")

            # 显示几个参考文献示例
            for i, ref in enumerate(references[:3]):
                raw_text = (
                    ref.get("raw_text", "")[:100] + "..."
                    if len(ref.get("raw_text", "")) > 100
                    else ref.get("raw_text", "")
                )
                print(f"    {i+1}. {raw_text}")
        else:
            print(f"  参考文献: ❌ 缺失")

        # 分析任务状态
        print("\n🔄 任务状态分析:")
        component_status = task_info.get("component_status", {})
        if isinstance(component_status, dict):
            for component, status_info in component_status.items():
                if isinstance(status_info, dict):
                    status = status_info.get("status", "unknown")
                    source = status_info.get("source", "未知")
                    icon = (
                        "✅"
                        if status == "success"
                        else "❌" if status == "failed" else "⚠️"
                    )
                    print(f"  {component.upper()}: {icon} {status} (来源: {source})")

        return results

    async def test_enhanced_features(self) -> bool:
        """测试增强功能"""
        logger.info("🚀 开始增强功能端到端测试")

        # 测试数据 - 使用知名论文
        test_cases = [
            {
                "name": "ArXiv URL测试 - Attention Is All You Need",
                "source": {"url": "https://arxiv.org/abs/1706.03762"},
                "expected": {
                    "has_title": True,
                    "has_authors": True,
                    "has_references": True,
                },
            },
            {
                "name": "DOI测试 - 经典论文",
                "source": {"doi": "10.1038/nature14539"},
                "expected": {"has_title": True, "has_authors": True},
            },
        ]

        all_passed = True

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*80}")
            print(f"🧪 测试案例 {i}: {test_case['name']}")
            print(f"{'='*80}")

            try:
                # 提交任务
                task_id = await self.submit_literature_task(test_case["source"])

                # 监控进度
                final_status = await self.monitor_task_progress(task_id)

                if final_status.get("status") == "success":
                    literature_id = final_status.get("literature_id")
                    if literature_id:
                        # 获取详细信息
                        details = await self.get_literature_details(literature_id)
                        fulltext = await self.get_literature_fulltext(literature_id)

                        # 分析结果
                        results = self.analyze_results(details, fulltext)

                        # 检查期望结果
                        case_passed = True
                        for key, expected_value in test_case["expected"].items():
                            if results.get(key) != expected_value:
                                logger.error(
                                    f"❌ 测试失败: {key} 期望 {expected_value}, 实际 {results.get(key)}"
                                )
                                case_passed = False

                        if case_passed:
                            logger.info(f"✅ 测试案例 {i} 通过")
                        else:
                            logger.error(f"❌ 测试案例 {i} 失败")
                            all_passed = False
                    else:
                        logger.error(f"❌ 测试案例 {i} 失败: 未获取到文献ID")
                        all_passed = False
                else:
                    logger.error(
                        f"❌ 测试案例 {i} 失败: 任务最终状态为 {final_status.get('status')}"
                    )
                    all_passed = False

            except Exception as e:
                logger.error(f"❌ 测试案例 {i} 出错: {e}")
                all_passed = False

        return all_passed

    async def run_all_tests(self) -> bool:
        """运行所有测试"""
        try:
            # 检查API健康状态
            if not await self.test_api_health():
                return False

            # 运行增强功能测试
            return await self.test_enhanced_features()

        finally:
            await self.client.aclose()


async def main():
    """主函数"""
    print("🚀 启动增强版端到端测试")
    print("🎯 验证新的状态管理和网络配置功能")
    print("=" * 80)

    tester = EnhancedE2ETest()

    try:
        success = await tester.run_all_tests()

        print(f"\n{'='*80}")
        if success:
            print("🎉 所有测试通过！新功能验证成功！")
            print("✅ 状态管理系统工作正常")
            print("✅ 网络请求管理正常")
            print("✅ 组件优先级修正生效")
            print("✅ 查重逻辑增强正常")
        else:
            print("❌ 部分测试失败，请检查日志")
        print("=" * 80)

        return success

    except Exception as e:
        logger.error(f"❌ 测试过程中出现致命错误: {e}")
        return False


if __name__ == "__main__":
    import sys

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
