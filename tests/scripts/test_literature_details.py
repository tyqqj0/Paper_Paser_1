#!/usr/bin/env python3
"""
测试文献详情查看
"""


import requests


def test_literature_details():
    """测试文献详情查看"""

    # 使用最新成功创建的文献ID
    literature_id = "6876210b2cc54c95eec2dec2"

    print(f"🔍 查看文献详情: {literature_id}")

    # 1. 通过API获取文献详情
    print("\n📖 通过API获取文献详情...")
    try:
        response = requests.get(f"http://localhost:8000/api/literature/{literature_id}")

        if response.status_code == 200:
            literature_data = response.json()
            print("   ✅ 成功获取文献数据")

            # 检查基本信息
            metadata = literature_data.get("metadata", {})
            print(f"   📄 标题: {metadata.get('title', 'N/A')}")
            print(f"   👥 作者: {len(metadata.get('authors', []))} 个")
            print(f"   📅 年份: {metadata.get('year', 'N/A')}")
            print(f"   📚 期刊: {metadata.get('journal', 'N/A')}")

            # 检查参考文献
            references = literature_data.get("references", [])
            print(f"   📋 参考文献数量: {len(references)}")

            if references:
                print("\n🔗 参考文献详情:")
                for i, ref in enumerate(references[:3]):  # 显示前3个
                    print(f"   {i+1}. 来源: {ref.get('source', 'N/A')}")
                    print(f"      原文: {ref.get('raw_text', 'N/A')[:100]}...")

                    parsed = ref.get("parsed", {})
                    print(f"      标题: {parsed.get('title', 'N/A')[:60]}...")
                    print(f"      作者: {len(parsed.get('authors', []))} 个")
                    print(f"      年份: {parsed.get('year', 'N/A')}")
                    print(f"      期刊: {parsed.get('venue', 'N/A')}")
                    print()

                if len(references) > 3:
                    print(f"   ... 还有 {len(references) - 3} 个参考文献")
            else:
                print("   ❌ 没有找到参考文献")

        else:
            print(f"   ❌ 获取文献详情失败: {response.status_code}")
            print(f"   错误: {response.text}")

    except Exception as e:
        print(f"   ❌ 请求失败: {e}")

    # 2. 直接从MongoDB获取数据
    print("\n🗄️ 直接从MongoDB获取数据...")
    try:
        import subprocess

        # 使用正确的容器名称
        cmd = f'''docker exec paper_paser_1-db-1 mongosh --quiet --eval "
        db = db.getSiblingDB('literature_parser');
        result = db.literatures.findOne({{_id: ObjectId('{literature_id}')}});
        if (result) {{
            print('找到文献数据:');
            print('标题:', result.metadata?.title || 'N/A');
            print('参考文献数量:', result.references?.length || 0);
            if (result.references && result.references.length > 0) {{
                print('第一个参考文献来源:', result.references[0].source || 'N/A');
                print('第一个参考文献标题:', result.references[0].parsed?.title?.substring(0, 60) || 'N/A');
            }}
        }} else {{
            print('未找到文献数据');
        }}
        "'''

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print("   MongoDB查询结果:")
            print(f"   {result.stdout}")
        else:
            print(f"   ❌ MongoDB查询失败: {result.stderr}")

    except Exception as e:
        print(f"   ❌ MongoDB查询失败: {e}")


if __name__ == "__main__":
    test_literature_details()
