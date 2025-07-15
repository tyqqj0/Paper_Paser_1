#!/usr/bin/env python3
"""
检查文献详情
"""

import requests
import json


def check_literature(lit_id):
    """检查指定文献的详情"""
    print(f"🔍 检查文献详情: {lit_id}")
    print("=" * 60)

    try:
        response = requests.get(
            f"http://localhost:8000/api/literature/{lit_id}", timeout=10
        )

        if response.status_code == 200:
            lit_info = response.json()

            print("✅ 成功获取文献信息")
            print("\n📋 完整信息:")
            print(json.dumps(lit_info, indent=2, ensure_ascii=False))

            print("\n📊 关键信息摘要:")

            # 基本标识
            identifiers = lit_info.get("identifiers", {})
            print(f"🔗 DOI: {identifiers.get('doi', '无')}")
            print(f"📄 ArXiv ID: {identifiers.get('arxiv_id', '无')}")

            # 元数据
            metadata = lit_info.get("metadata", {})
            print(f"📰 标题: {metadata.get('title', '未知')}")
            print(f"📅 年份: {metadata.get('year', '未知')}")
            print(f"📖 期刊: {metadata.get('journal', '未知')}")

            # 作者
            authors = metadata.get("authors", [])
            print(f"👥 作者数量: {len(authors)}")
            if authors:
                author_names = [
                    author.get("full_name", "未知") for author in authors[:3]
                ]
                print(
                    f"👥 作者列表: {', '.join(author_names)}"
                    + (" ..." if len(authors) > 3 else "")
                )

            # 参考文献
            references = lit_info.get("references", [])
            print(f"📚 参考文献数量: {len(references)}")

            # 内容信息
            content = lit_info.get("content", {})
            print(f"🔗 PDF URL: {content.get('pdf_url', '无')}")
            print(f"🌐 源页面: {content.get('source_page_url', '无')}")

            return True

        else:
            print(f"❌ 获取失败: {response.status_code}")
            print(f"📄 响应: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 获取异常: {e}")
        return False


def main():
    # 检查已知的文献ID
    literature_ids = [
        "68760017cce9ba724afaeb57",  # 已存在的DOI文献
        "68760549f37894a3193cd04b",  # 测试文献
        "687604a75a9710ea87b745ac",  # 另一个文献
    ]

    for lit_id in literature_ids:
        check_literature(lit_id)
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
