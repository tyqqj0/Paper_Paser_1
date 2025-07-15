#!/usr/bin/env python3
"""
元数据获取调试脚本
测试CrossRef、Semantic Scholar、GROBID等外部API服务
"""

import asyncio

import httpx


class MetadataDebugger:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def test_crossref_api(self, doi: str = "10.1038/nature12373"):
        """测试CrossRef API"""
        print(f"\n🔍 测试CrossRef API - DOI: {doi}")
        try:
            url = f"https://api.crossref.org/works/{doi}"
            headers = {
                "User-Agent": "Literature-Parser/1.0 (mailto:literature-parser@example.com)",
            }

            response = await self.client.get(url, headers=headers)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                work = data.get("message", {})

                title = (
                    work.get("title", ["Unknown"])[0]
                    if work.get("title")
                    else "Unknown"
                )
                authors = []
                for author in work.get("author", []):
                    given = author.get("given", "")
                    family = author.get("family", "")
                    authors.append(f"{given} {family}".strip())

                print(f"✅ 标题: {title}")
                print(
                    f"✅ 作者: {', '.join(authors[:3])}"
                    + (" ..." if len(authors) > 3 else ""),
                )
                print(
                    f"✅ 年份: {work.get('published-print', {}).get('date-parts', [[None]])[0][0]}",
                )
                print(f"✅ 期刊: {work.get('container-title', ['Unknown'])[0]}")
                return True
            else:
                print(f"❌ CrossRef API错误: {response.status_code}")
                print(f"响应: {response.text[:200]}...")
                return False

        except Exception as e:
            print(f"❌ CrossRef API异常: {e}")
            return False

    async def test_semantic_scholar_api(self, doi: str = "10.1038/nature12373"):
        """测试Semantic Scholar API"""
        print(f"\n🔍 测试Semantic Scholar API - DOI: {doi}")
        try:
            # 通过DOI搜索
            search_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            params = {
                "fields": "title,authors,year,journal,referenceCount,citationCount,references.title,references.authors",
            }

            response = await self.client.get(search_url, params=params)
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()

                title = data.get("title", "Unknown")
                authors = [
                    author.get("name", "Unknown") for author in data.get("authors", [])
                ]
                year = data.get("year")
                journal = (
                    data.get("journal", {}).get("name", "Unknown")
                    if data.get("journal")
                    else "Unknown"
                )
                ref_count = data.get("referenceCount", 0)

                print(f"✅ 标题: {title}")
                print(
                    f"✅ 作者: {', '.join(authors[:3])}"
                    + (" ..." if len(authors) > 3 else ""),
                )
                print(f"✅ 年份: {year}")
                print(f"✅ 期刊: {journal}")
                print(f"✅ 参考文献数量: {ref_count}")

                # 测试参考文献获取
                references = data.get("references", [])
                print(f"✅ 获取到参考文献: {len(references)} 条")

                return True
            else:
                print(f"❌ Semantic Scholar API错误: {response.status_code}")
                print(f"响应: {response.text[:200]}...")
                return False

        except Exception as e:
            print(f"❌ Semantic Scholar API异常: {e}")
            return False

    async def test_grobid_api(self):
        """测试GROBID API"""
        print("\n🔍 测试GROBID API")
        try:
            # 测试健康检查
            health_url = "http://localhost:8070/api/isalive"
            response = await self.client.get(health_url)
            print(f"健康检查状态码: {response.status_code}")

            if response.status_code == 200:
                print("✅ GROBID服务运行正常")

                # 测试PDF处理功能（使用示例PDF URL）
                process_url = "http://localhost:8070/api/processFulltextDocument"

                # 这里可以添加实际的PDF测试
                print("✅ GROBID API可访问（需要PDF文件进行完整测试）")
                return True
            else:
                print(f"❌ GROBID健康检查失败: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ GROBID API异常: {e}")
            return False

    async def test_literature_api(self):
        """测试本地Literature API"""
        print("\n🔍 测试Literature Parser API")
        try:
            # 测试健康检查
            health_url = "http://localhost:8000/api/health"
            response = await self.client.get(health_url)
            print(f"健康检查状态码: {response.status_code}")

            if response.status_code == 200:
                print("✅ Literature Parser API运行正常")

                # 测试提交文献
                submit_url = "http://localhost:8000/api/literature"
                test_data = {"doi": "10.1038/nature12373"}

                submit_response = await self.client.post(submit_url, json=test_data)
                print(f"提交任务状态码: {submit_response.status_code}")

                if submit_response.status_code == 200:
                    result = submit_response.json()
                    print(f"✅ 任务提交成功: {result}")
                    return True
                else:
                    print(f"❌ 任务提交失败: {submit_response.text}")
                    return False

            else:
                print(f"❌ API健康检查失败: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Literature API异常: {e}")
            return False

    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始元数据获取功能调试")
        print("=" * 50)

        tests = [
            ("CrossRef API", self.test_crossref_api),
            ("Semantic Scholar API", self.test_semantic_scholar_api),
            ("GROBID API", self.test_grobid_api),
            ("Literature Parser API", self.test_literature_api),
        ]

        results = {}

        for test_name, test_func in tests:
            print(f"\n{'=' * 20} {test_name} {'=' * 20}")
            try:
                result = await test_func()
                results[test_name] = result
            except Exception as e:
                print(f"❌ {test_name} 测试异常: {e}")
                results[test_name] = False

        # 总结
        print(f"\n{'=' * 50}")
        print("🎯 测试总结")
        print("=" * 50)

        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{test_name}: {status}")

        success_count = sum(1 for r in results.values() if r)
        total_count = len(results)

        print(f"\n总体结果: {success_count}/{total_count} 测试通过")

        if success_count == total_count:
            print("🎉 所有测试都通过了！元数据获取功能正常")
        else:
            print("⚠️  部分测试失败，需要进一步调试")

        await self.client.aclose()


async def main():
    debugger = MetadataDebugger()
    await debugger.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
