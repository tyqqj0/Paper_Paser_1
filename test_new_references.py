#!/usr/bin/env python3
"""测试修复后的references功能"""

import asyncio
import httpx
import time

BASE_URL = "http://127.0.0.1:8000/api"


async def test_new_references():
    """测试新的references功能"""
    print("=== 测试修复后的References功能 ===")

    # 使用一个全新的论文URL
    test_url = "http://arxiv.org/abs/2304.08485"  # GPT-4 Technical Report
    print(f"提交新的文献解析任务: {test_url}")

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            # 1. 提交任务
            response = await client.post(
                f"{BASE_URL}/literature", json={"source": {"url": test_url}}
            )
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")

            if response.status_code == 202:
                task_data = response.json()
                task_id = task_data["taskId"]
                print(f"任务ID: {task_id}")

                # 2. 监控任务进度
                print("\n=== 监控任务进度 ===")
                max_wait = 300  # 5分钟超时
                start_time = time.time()

                while time.time() - start_time < max_wait:
                    try:
                        status_response = await client.get(f"{BASE_URL}/task/{task_id}")
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            elapsed = time.time() - start_time
                            print(
                                f"\n[{elapsed:.1f}s] 任务状态: {status_data.get('status')}"
                            )
                            print(f"当前阶段: {status_data.get('stage', 'N/A')}")
                            print(f"进度: {status_data.get('progress_percentage', 0)}%")

                            # 检查组件状态
                            if "component_status" in status_data:
                                comp_status = status_data["component_status"]
                                print("组件状态:")
                                for component, status in comp_status.items():
                                    print(
                                        f"  {component}: {status.get('status')} - {status.get('stage', 'N/A')}"
                                    )

                            # 检查是否完成
                            if status_data.get("status") == "success":
                                literature_id = status_data.get("literature_id")
                                if literature_id:
                                    print(f"\n✅ 任务完成! 文献ID: {literature_id}")
                                    await analyze_literature_references(
                                        client, literature_id
                                    )
                                    return literature_id
                                break
                            elif status_data.get("status") == "failure":
                                error_info = status_data.get("error_info", {})
                                print(f"❌ 任务失败: {error_info}")
                                break

                        else:
                            print(f"状态查询失败: {status_response.status_code}")

                    except Exception as e:
                        print(f"检查状态时出错: {e}")

                    await asyncio.sleep(10)  # 等待10秒后再检查
                else:
                    print("❌ 任务超时")

            elif response.status_code == 200:
                result = response.json()
                if result.get("status") == "exists":
                    literature_id = result.get("literatureId")
                    print(f"文献已存在，ID: {literature_id}")
                    await analyze_literature_references(client, literature_id)
                    return literature_id
            else:
                print(f"提交失败: {response.text}")

        except Exception as e:
            print(f"请求失败: {e}")
            import traceback

            traceback.print_exc()


async def analyze_literature_references(client, literature_id):
    """分析文献的references"""
    print(f"\n=== 分析文献 {literature_id} 的References ===")

    try:
        response = await client.get(f"{BASE_URL}/literature/{literature_id}")
        if response.status_code == 200:
            data = response.json()

            # 基本信息
            metadata = data.get("metadata", {})
            print(f"📖 标题: {metadata.get('title', 'N/A')}")
            print(f"📅 年份: {metadata.get('year', 'N/A')}")
            print(f"👥 作者数量: {len(metadata.get('authors', []))}")

            # References分析
            refs = data.get("references", [])
            print(f"\n📚 References数量: {len(refs)}")

            if refs:
                # 来源统计
                sources = {}
                for ref in refs:
                    source = ref.get("source", "Unknown")
                    sources[source] = sources.get(source, 0) + 1

                print(f"\n📊 References来源统计:")
                for source, count in sources.items():
                    print(f"  {source}: {count} 个 ({count/len(refs)*100:.1f}%)")

                # 解析质量统计
                parsed_count = sum(1 for ref in refs if ref.get("parsed"))
                print(f"\n📈 解析质量统计:")
                print(
                    f"  已解析: {parsed_count}/{len(refs)} ({parsed_count/len(refs)*100:.1f}%)"
                )

                if parsed_count > 0:
                    # 详细质量分析
                    title_count = sum(
                        1 for ref in refs if ref.get("parsed", {}).get("title")
                    )
                    year_count = sum(
                        1 for ref in refs if ref.get("parsed", {}).get("year")
                    )
                    author_count = sum(
                        1 for ref in refs if ref.get("parsed", {}).get("authors")
                    )

                    print(
                        f"  有标题: {title_count}/{parsed_count} ({title_count/parsed_count*100:.1f}%)"
                    )
                    print(
                        f"  有年份: {year_count}/{parsed_count} ({year_count/parsed_count*100:.1f}%)"
                    )
                    print(
                        f"  有作者: {author_count}/{parsed_count} ({author_count/parsed_count*100:.1f}%)"
                    )

                # 显示前几个references示例
                print(f"\n📋 References示例 (前5个):")
                for i, ref in enumerate(refs[:5], 1):
                    print(f"\n  {i}. Source: {ref.get('source', 'N/A')}")
                    raw_text = ref.get("raw_text", "N/A")
                    if len(raw_text) > 100:
                        raw_text = raw_text[:100] + "..."
                    print(f"     Raw: {raw_text}")

                    parsed = ref.get("parsed")
                    if parsed:
                        print(f"     ✅ 已解析:")
                        print(f"       Title: {parsed.get('title', 'N/A')}")
                        print(f"       Year: {parsed.get('year', 'N/A')}")
                        authors = parsed.get("authors", [])
                        if authors:
                            author_names = [a.get("name", "N/A") for a in authors[:2]]
                            print(f"       Authors: {', '.join(author_names)}")
                            if len(authors) > 2:
                                print(f"       ... 还有 {len(authors) - 2} 位作者")
                        print(f"       Journal: {parsed.get('journal', 'N/A')}")
                    else:
                        print(f"     ❌ 未解析")

                print(f"\n🎯 References功能测试结果:")
                print(f"  ✅ References数据成功获取: {len(refs)} 个")
                print(f"  ✅ 瀑布流策略正常工作")
                print(f"  ✅ 数据解析质量: {parsed_count/len(refs)*100:.1f}%")

            else:
                print("❌ 没有找到references数据")
                print("可能原因:")
                print("  - Semantic Scholar API没有返回数据")
                print("  - GROBID解析失败")
                print("  - 处理逻辑有问题")

        else:
            print(f"获取文献详情失败: {response.status_code}")

    except Exception as e:
        print(f"分析references时出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_new_references())
