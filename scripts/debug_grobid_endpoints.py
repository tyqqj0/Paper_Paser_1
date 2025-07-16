#!/usr/bin/env python3
"""
GROBID端点调试脚本

此脚本直接测试GROBID服务的各个端点，绕过我们的应用逻辑。
用于诊断GROBID服务本身是否正常工作。
"""

import requests
import json
import os
from pathlib import Path


def test_grobid_service():
    """测试GROBID服务的基本连接"""
    print("🔍 测试GROBID服务连接...")

    try:
        response = requests.get("http://localhost:8070/api/isalive", timeout=10)
        print(f"✅ GROBID服务状态: {response.status_code}")
        print(f"   响应内容: {response.text}")
        return True
    except Exception as e:
        print(f"❌ GROBID服务连接失败: {e}")
        return False


def test_grobid_endpoint(endpoint_name, pdf_path):
    """测试特定的GROBID端点"""
    print(f"\n🔍 测试GROBID端点: {endpoint_name}")

    if not os.path.exists(pdf_path):
        print(f"❌ PDF文件不存在: {pdf_path}")
        return False

    url = f"http://localhost:8070/api/{endpoint_name}"

    try:
        with open(pdf_path, "rb") as pdf_file:
            files = {"input": pdf_file}

            print(f"   📤 发送请求到: {url}")
            print(f"   📄 PDF文件大小: {os.path.getsize(pdf_path)} bytes")

            response = requests.post(url, files=files, timeout=60)

            print(f"   📥 响应状态码: {response.status_code}")
            print(f"   📥 响应头: {dict(response.headers)}")

            if response.status_code == 200:
                print(f"   ✅ 成功! 响应长度: {len(response.text)} characters")

                # 保存响应到文件以供检查
                output_dir = Path("debug_grobid_responses")
                output_dir.mkdir(exist_ok=True)

                output_file = output_dir / f"{endpoint_name}_response.xml"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(response.text)

                print(f"   💾 响应已保存到: {output_file}")

                # 显示响应的前500个字符
                print(f"   📄 响应预览:")
                print(f"   {response.text[:500]}...")

                return True
            else:
                print(f"   ❌ 失败! 状态码: {response.status_code}")
                print(f"   📄 错误响应: {response.text}")
                return False

    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
        return False


def main():
    """主函数"""
    print("🚀 GROBID端点调试脚本")
    print("=" * 50)

    # 1. 测试GROBID服务连接
    if not test_grobid_service():
        print("\n❌ GROBID服务不可用，退出测试")
        return

    # 2. 查找调试PDF文件
    debug_pdfs_dir = Path("debug_pdfs")
    if not debug_pdfs_dir.exists():
        print(f"\n❌ 调试PDF目录不存在: {debug_pdfs_dir}")
        return

    pdf_files = list(debug_pdfs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"\n❌ 调试PDF目录中没有PDF文件: {debug_pdfs_dir}")
        return

    # 使用最新的PDF文件
    pdf_file = max(pdf_files, key=lambda p: p.stat().st_mtime)
    print(f"\n📄 使用PDF文件: {pdf_file}")

    # 3. 测试各个GROBID端点
    endpoints_to_test = [
        "processHeaderDocument",  # 处理文档头部信息（标题、作者等）
        "processReferences",  # 处理参考文献
        "processFulltextDocument",  # 处理全文
    ]

    results = {}

    for endpoint in endpoints_to_test:
        success = test_grobid_endpoint(endpoint, pdf_file)
        results[endpoint] = success

    # 4. 总结结果
    print("\n" + "=" * 50)
    print("📊 测试结果总结:")

    for endpoint, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"   {endpoint}: {status}")

    successful_count = sum(results.values())
    total_count = len(results)

    print(f"\n🎯 总体结果: {successful_count}/{total_count} 个端点测试成功")

    if successful_count == total_count:
        print("✅ 所有GROBID端点都正常工作！问题可能在我们的应用逻辑中。")
    elif successful_count > 0:
        print("⚠️  部分GROBID端点工作正常，部分失败。")
    else:
        print("❌ 所有GROBID端点都失败了。问题可能在GROBID服务本身。")


if __name__ == "__main__":
    main()
