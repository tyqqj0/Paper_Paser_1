#!/usr/bin/env python3
"""测试API响应的详细信息"""

import json

import httpx


def main():
    try:
        response = httpx.get(
            "http://localhost:8000/api/literature/68760017cce9ba724afaeb57",
        )

        if response.status_code == 200:
            data = response.json()

            print("📊 API响应分析:")
            print("=" * 50)

            # 检查顶级字段
            print("🔍 顶级字段:")
            for key in sorted(data.keys()):
                value = data[key]
                if isinstance(value, dict):
                    print(f"   {key}: dict({len(value)} keys)")
                elif isinstance(value, list):
                    print(f"   {key}: list({len(value)} items)")
                else:
                    print(f"   {key}: {value}")

            # 检查便利字段
            print("\n🎯 便利字段:")
            print(f"   title: {data.get('title', 'N/A')}")
            print(f"   authors: {data.get('authors', [])}")
            print(f"   year: {data.get('year', 'N/A')}")
            print(f"   journal: {data.get('journal', 'N/A')}")
            print(f"   doi: {data.get('doi', 'N/A')}")

            # 检查metadata内容
            metadata = data.get("metadata", {})
            print("\n📋 Metadata内容:")
            print(f"   CrossRef: {'✅' if metadata.get('crossref') else '❌'}")
            print(
                f"   Semantic Scholar: {'✅' if metadata.get('semantic_scholar') else '❌'}",
            )
            print(f"   GROBID: {'✅' if metadata.get('grobid') else '❌'}")

            # 如果有metadata，显示详细信息
            if metadata.get("crossref"):
                crossref = metadata["crossref"]
                print(f"   CrossRef标题: {crossref.get('title', 'N/A')}")

            if metadata.get("semantic_scholar"):
                ss = metadata["semantic_scholar"]
                print(f"   Semantic Scholar标题: {ss.get('title', 'N/A')}")

            # 检查identifiers
            identifiers = data.get("identifiers", {})
            print("\n🆔 Identifiers:")
            print(f"   DOI: {identifiers.get('doi', 'N/A')}")
            print(f"   ArXiv: {identifiers.get('arxiv_id', 'N/A')}")

            # 输出完整JSON用于调试
            print("\n📄 完整响应 (前500字符):")
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            print(json_str[:500] + "..." if len(json_str) > 500 else json_str)

        else:
            print(f"❌ API请求失败: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    main()
