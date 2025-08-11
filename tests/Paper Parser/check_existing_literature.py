#!/usr/bin/env python3
"""检查已存在文献的references"""

import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000/api"


async def check_existing_literature():
    """检查已存在文献的references"""
    print("=== 检查已存在文献的References ===")

    # 已知的文献ID
    literature_id = "6877a57f80b8945ed44473a4"

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            # 获取文献详情
            response = await client.get(f"{BASE_URL}/literature/{literature_id}")
            print(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                lit_data = response.json()
                print(f"\n=== 文献详情 ===")
                print(f"ID: {literature_id}")
                print(f"标题: {lit_data.get('metadata', {}).get('title', 'N/A')}")

                # 检查references
                refs = lit_data.get("references", [])
                print(f"References数量: {len(refs)}")

                if refs:
                    print("\nReferences详情:")
                    for i, ref in enumerate(refs[:5], 1):  # 显示前5个
                        raw_text = ref.get("raw_text", "N/A")
                        if len(raw_text) > 100:
                            raw_text = raw_text[:100] + "..."
                        print(f"  {i}. Raw: {raw_text}")
                        print(f"     Source: {ref.get('source', 'N/A')}")
                        print(f"     Parsed: {bool(ref.get('parsed'))}")
                        if ref.get("parsed"):
                            parsed = ref.get("parsed")
                            print(f"     -> Title: {parsed.get('title', 'N/A')}")
                            print(f"     -> Year: {parsed.get('year', 'N/A')}")
                            print(f"     -> Authors: {parsed.get('authors', [])}")
                        print()

                    if len(refs) > 5:
                        print(f"  ... 还有 {len(refs) - 5} 个references")

                    # 分析references来源
                    sources = {}
                    for ref in refs:
                        source = ref.get("source", "Unknown")
                        sources[source] = sources.get(source, 0) + 1

                    print(f"\n=== References来源统计 ===")
                    for source, count in sources.items():
                        print(f"  {source}: {count} 个")

                    # 检查parsed比例
                    parsed_count = sum(1 for ref in refs if ref.get("parsed"))
                    print(f"\n=== 解析统计 ===")
                    print(
                        f"已解析: {parsed_count}/{len(refs)} ({parsed_count/len(refs)*100:.1f}%)"
                    )

                else:
                    print("❌ 没有找到references数据")

                # 检查content和metadata
                print(f"\n=== 其他信息 ===")
                content = lit_data.get("content", {})
                print(f"PDF URL: {content.get('pdf_url', 'N/A')}")
                print(f"有全文内容: {bool(content.get('fulltext'))}")

                metadata = lit_data.get("metadata", {})
                print(f"作者数量: {len(metadata.get('authors', []))}")
                print(f"年份: {metadata.get('year', 'N/A')}")
                print(f"期刊: {metadata.get('journal', 'N/A')}")

            else:
                print(f"获取文献详情失败: {response.status_code}")
                print(f"错误信息: {response.text}")

        except Exception as e:
            print(f"请求失败: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_existing_literature())
