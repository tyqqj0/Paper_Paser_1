#!/usr/bin/env python3
"""
完整系统测试脚本
测试URL解析、实际数据获取、数据库存储等功能
"""

import asyncio
import time
from typing import Any, Dict

import httpx
import motor.motor_asyncio
from bson import ObjectId

# 服务配置
API_BASE_URL = "http://localhost:8000"
MONGODB_URL = "mongodb://literature_parser_backend:literature_parser_backend@localhost:27017/admin"


class SystemTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)
        self.mongo_client = None
        self.db = None

    async def setup(self):
        """初始化连接"""
        print("🔧 初始化测试环境...")
        try:
            # 连接MongoDB
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
            self.db = self.mongo_client.admin
            await self.db.command("ping")
            print("✅ MongoDB连接成功")
        except Exception as e:
            print(f"❌ MongoDB连接失败: {e}")
            raise

    async def cleanup(self):
        """清理资源"""
        if self.client:
            await self.client.aclose()
        if self.mongo_client:
            self.mongo_client.close()

    async def test_api_health(self) -> bool:
        """测试API健康状态"""
        print("\n🏥 测试API健康状态...")
        try:
            response = await self.client.get(f"{API_BASE_URL}/api/health")
            if response.status_code == 200:
                print("✅ API服务正常")
                return True
            else:
                print(f"❌ API服务异常: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API连接失败: {e}")
            return False

    async def test_database_status(self) -> bool:
        """检查数据库状态"""
        print("\n🗄️ 检查数据库状态...")
        try:
            # 检查集合
            collections = await self.db.list_collection_names()
            print(f"📚 数据库集合: {collections}")

            # 检查文献数量
            if "literature" in collections:
                lit_count = await self.db.literature.count_documents({})
                print(f"📄 文献文档数量: {lit_count}")

                if lit_count > 0:
                    # 展示最近文档
                    recent = (
                        await self.db.literature.find({})
                        .sort("created_at", -1)
                        .limit(1)
                        .to_list(1)
                    )
                    if recent:
                        doc = recent[0]
                        print("📋 最新文档:")
                        print(f"   ID: {doc.get('_id')}")
                        print(f"   标题: {doc.get('title', 'N/A')}")
                        print(f"   DOI: {doc.get('doi', 'N/A')}")
                        print(f"   作者数: {len(doc.get('authors', []))}")
                        print(f"   参考文献数: {len(doc.get('references', []))}")
                        print(f"   处理状态: {doc.get('processing_status', 'N/A')}")

            # 检查任务数量
            if "tasks" in collections:
                task_count = await self.db.tasks.count_documents({})
                print(f"🔧 任务文档数量: {task_count}")

            return True

        except Exception as e:
            print(f"❌ 数据库检查失败: {e}")
            return False

    async def test_literature_processing(
        self,
        test_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """测试文献处理流程"""
        print("\n📖 测试文献处理...")
        print(f"   测试数据: {test_data}")

        try:
            # 1. 提交处理请求
            print("1️⃣ 提交处理请求...")
            response = await self.client.post(
                f"{API_BASE_URL}/api/literature",
                json=test_data,
            )

            print(f"   状态码: {response.status_code}")
            result_data = response.json()
            print(f"   响应数据: {result_data}")

            if response.status_code == 202:
                # 新任务
                task_id = result_data.get("taskId")
                print(f"✅ 新任务创建: {task_id}")

                # 2. 监控任务进度
                print("2️⃣ 监控任务进度...")
                literature_id = await self.monitor_task_progress(task_id)

                if literature_id:
                    # 3. 获取处理结果
                    return await self.get_literature_details(literature_id)
                else:
                    return {"error": "任务处理失败"}

            elif response.status_code == 200:
                # 已存在文献
                literature_id = result_data.get("literatureId")
                print(f"✅ 文献已存在: {literature_id}")
                return await self.get_literature_details(literature_id)
            else:
                return {"error": f"请求失败: {response.status_code}"}

        except Exception as e:
            print(f"❌ 文献处理测试失败: {e}")
            return {"error": str(e)}

    async def monitor_task_progress(self, task_id: str, max_wait: int = 120) -> str:
        """监控任务进度"""
        print(f"   监控任务: {task_id}")

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = await self.client.get(f"{API_BASE_URL}/api/task/{task_id}")
                if response.status_code == 200:
                    task_data = response.json()
                    status = task_data.get("status")
                    stage = task_data.get("stage", "N/A")
                    progress = task_data.get("progress", "N/A")

                    print(f"   📊 状态: {status} | 阶段: {stage} | 进度: {progress}%")

                    if status == "success":
                        literature_id = task_data.get("result", {}).get("literature_id")
                        print(f"   🎉 任务完成！文献ID: {literature_id}")
                        return literature_id
                    elif status == "failure":
                        error = task_data.get("error", "未知错误")
                        print(f"   ❌ 任务失败: {error}")
                        return None

                await asyncio.sleep(2)

            except Exception as e:
                print(f"   ❌ 查询任务状态失败: {e}")
                await asyncio.sleep(2)

        print(f"   ⏰ 任务超时 ({max_wait}秒)")
        return None

    async def get_literature_details(self, literature_id: str) -> Dict[str, Any]:
        """获取文献详细信息"""
        print(f"3️⃣ 获取文献详情: {literature_id}")

        try:
            # 通过API获取
            response = await self.client.get(
                f"{API_BASE_URL}/api/literature/{literature_id}",
            )
            if response.status_code == 200:
                api_data = response.json()
                print("✅ 通过API获取成功")

                # 直接从MongoDB获取完整数据
                mongo_data = await self.db.literature.find_one(
                    {"_id": ObjectId(literature_id)},
                )

                # 分析数据质量
                analysis = self.analyze_literature_data(api_data, mongo_data)

                return {
                    "api_data": api_data,
                    "mongo_data": mongo_data,
                    "analysis": analysis,
                }
            else:
                print(f"❌ API获取失败: {response.status_code}")
                return {"error": f"API获取失败: {response.status_code}"}

        except Exception as e:
            print(f"❌ 获取文献详情失败: {e}")
            return {"error": str(e)}

    def analyze_literature_data(
        self,
        api_data: Dict,
        mongo_data: Dict,
    ) -> Dict[str, Any]:
        """分析文献数据质量"""
        print("📊 分析数据质量...")

        analysis = {
            "basic_info": {},
            "content_analysis": {},
            "metadata_analysis": {},
            "references_analysis": {},
        }

        # 基本信息分析
        analysis["basic_info"] = {
            "title_available": bool(
                api_data.get("title") and api_data["title"] != "Unknown Title",
            ),
            "authors_count": len(api_data.get("authors", [])),
            "doi_available": bool(api_data.get("doi")),
            "year_available": bool(api_data.get("year")),
            "journal_available": bool(api_data.get("journal")),
        }

        # 内容分析
        content = mongo_data.get("content", {}) if mongo_data else {}
        analysis["content_analysis"] = {
            "pdf_url_available": bool(content.get("pdf_url")),
            "download_status": content.get("status", "N/A"),
            "full_text_length": len(content.get("full_text", "")),
            "has_sections": bool(content.get("sections")),
        }

        # 元数据分析
        metadata = mongo_data.get("metadata", {}) if mongo_data else {}
        analysis["metadata_analysis"] = {
            "crossref_data": bool(metadata.get("crossref")),
            "semantic_scholar_data": bool(metadata.get("semantic_scholar")),
            "grobid_data": bool(metadata.get("grobid")),
        }

        # 参考文献分析
        references = api_data.get("references", [])
        analysis["references_analysis"] = {
            "total_references": len(references),
            "references_with_doi": len([r for r in references if r.get("doi")]),
            "references_with_title": len([r for r in references if r.get("title")]),
            "data_sources": list(set([r.get("source", "unknown") for r in references])),
        }

        return analysis

    def print_analysis_summary(self, analysis: Dict[str, Any]):
        """打印分析摘要"""
        print("\n📋 数据质量分析摘要:")
        print("=" * 50)

        # 基本信息
        basic = analysis["basic_info"]
        print("📄 基本信息:")
        print(f"   标题可用: {'✅' if basic['title_available'] else '❌'}")
        print(f"   作者数量: {basic['authors_count']}")
        print(f"   DOI可用: {'✅' if basic['doi_available'] else '❌'}")
        print(f"   年份可用: {'✅' if basic['year_available'] else '❌'}")
        print(f"   期刊可用: {'✅' if basic['journal_available'] else '❌'}")

        # 内容分析
        content = analysis["content_analysis"]
        print("\n📄 内容分析:")
        print(f"   PDF URL: {'✅' if content['pdf_url_available'] else '❌'}")
        print(f"   下载状态: {content['download_status']}")
        print(f"   全文长度: {content['full_text_length']} 字符")
        print(f"   章节数据: {'✅' if content['has_sections'] else '❌'}")

        # 元数据分析
        metadata = analysis["metadata_analysis"]
        print("\n🔍 元数据来源:")
        print(f"   CrossRef: {'✅' if metadata['crossref_data'] else '❌'}")
        print(
            f"   Semantic Scholar: {'✅' if metadata['semantic_scholar_data'] else '❌'}",
        )
        print(f"   GROBID: {'✅' if metadata['grobid_data'] else '❌'}")

        # 参考文献分析
        refs = analysis["references_analysis"]
        print("\n📚 参考文献:")
        print(f"   总数量: {refs['total_references']}")
        print(f"   有DOI: {refs['references_with_doi']}")
        print(f"   有标题: {refs['references_with_title']}")
        print(f"   数据源: {', '.join(refs['data_sources'])}")


async def main():
    """主测试函数"""
    print("🚀 开始完整系统测试...")
    print("=" * 60)

    tester = SystemTester()

    try:
        await tester.setup()

        # 1. 测试API健康状态
        if not await tester.test_api_health():
            print("❌ API服务不可用，退出测试")
            return

        # 2. 测试数据库状态
        if not await tester.test_database_status():
            print("❌ 数据库不可用，退出测试")
            return

        # 3. 测试用例
        test_cases = [
            {
                "name": "Nature论文测试",
                "data": {"doi": "10.1038/nature12373", "title": None, "authors": None},
            },
            {
                "name": "arXiv论文测试",
                "data": {
                    "doi": None,
                    "title": "Attention Is All You Need",
                    "authors": ["Ashish Vaswani", "Noam Shazeer"],
                },
            },
            {
                "name": "URL直接测试",
                "data": {
                    "doi": None,
                    "title": "Deep Learning Paper",
                    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                },
            },
        ]

        print(f"\n🧪 将执行 {len(test_cases)} 个测试用例...")

        results = []
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"测试用例 {i}/{len(test_cases)}: {test_case['name']}")
            print(f"{'='*60}")

            result = await tester.test_literature_processing(test_case["data"])
            result["test_name"] = test_case["name"]
            results.append(result)

            if "analysis" in result:
                tester.print_analysis_summary(result["analysis"])
            elif "error" in result:
                print(f"❌ 测试失败: {result['error']}")

            # 短暂等待避免过载
            if i < len(test_cases):
                print("\n⏸️ 等待5秒后进行下一个测试...")
                await asyncio.sleep(5)

        # 4. 测试结果汇总
        print(f"\n{'='*60}")
        print("🏁 测试结果汇总")
        print(f"{'='*60}")

        successful_tests = [r for r in results if "analysis" in r]
        failed_tests = [r for r in results if "error" in r]

        print(f"✅ 成功测试: {len(successful_tests)}/{len(results)}")
        print(f"❌ 失败测试: {len(failed_tests)}/{len(results)}")

        if successful_tests:
            print("\n🎯 成功测试详情:")
            for result in successful_tests:
                analysis = result["analysis"]
                basic = analysis["basic_info"]
                refs = analysis["references_analysis"]
                print(
                    f"   • {result['test_name']}: "
                    f"作者{basic['authors_count']}人, "
                    f"参考文献{refs['total_references']}篇",
                )

        if failed_tests:
            print("\n💥 失败测试详情:")
            for result in failed_tests:
                print(f"   • {result['test_name']}: {result['error']}")

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await tester.cleanup()
        print("\n🏁 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
