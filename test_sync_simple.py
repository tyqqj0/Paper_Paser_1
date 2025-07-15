#!/usr/bin/env python3
"""
简单的同步测试脚本
测试同步化后的代码是否正常工作
"""

from literature_parser_backend.worker.tasks import extract_authoritative_identifiers


def test_identifier_extraction():
    """测试标识符提取功能（纯同步，无网络请求）"""
    print("🔍 测试标识符提取...")

    # 测试数据
    test_cases = [
        {
            "name": "DOI测试",
            "source": {"doi": "10.1038/nature12373"},
            "expected_primary": "doi",
        },
        {
            "name": "ArXiv测试",
            "source": {"arxiv_id": "2301.00001"},
            "expected_primary": "arxiv",
        },
        {
            "name": "URL中的DOI测试",
            "source": {"url": "https://doi.org/10.1038/nature12373"},
            "expected_primary": "doi",
        },
    ]

    success_count = 0

    for case in test_cases:
        try:
            identifiers, primary_type = extract_authoritative_identifiers(
                case["source"]
            )

            if primary_type == case["expected_primary"]:
                print(f"✅ {case['name']}: {primary_type}")
                success_count += 1
            else:
                print(
                    f"❌ {case['name']}: 期望 {case['expected_primary']}, 得到 {primary_type}"
                )

        except Exception as e:
            print(f"❌ {case['name']}: 错误 {e}")

    print(f"\n标识符提取测试: {success_count}/{len(test_cases)} 通过")
    return success_count == len(test_cases)


def test_basic_imports():
    """测试基本导入"""
    print("🔍 测试模块导入...")

    try:
        from literature_parser_backend.worker.content_fetcher import ContentFetcher
        from literature_parser_backend.worker.metadata_fetcher import MetadataFetcher
        from literature_parser_backend.worker.references_fetcher import (
            ReferencesFetcher,
        )

        print("✅ 所有Fetcher模块导入成功")

        from literature_parser_backend.services.crossref import CrossRefClient
        from literature_parser_backend.services.semantic_scholar import (
            SemanticScholarClient,
        )
        from literature_parser_backend.services.grobid import GrobidClient

        print("✅ 所有服务客户端导入成功")

        return True

    except Exception as e:
        print(f"❌ 导入错误: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("同步化修改验证测试")
    print("=" * 50)

    # 运行测试
    tests = [
        ("基本导入测试", test_basic_imports),
        ("标识符提取测试", test_identifier_extraction),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{test_name}")
        print("-" * 30)

        if test_func():
            passed += 1
            print(f"✅ {test_name} 通过")
        else:
            print(f"❌ {test_name} 失败")

    print(f"\n" + "=" * 50)
    print(f"总结: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！同步化修改成功！")
    else:
        print("⚠️  部分测试失败，需要进一步检查")
