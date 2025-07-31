#!/usr/bin/env python3
"""
测试PDF重定向器功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, '/home/parser/code/Paper_Paser_1')

from literature_parser_backend.services.url_mapping.core.pdf_redirector import get_pdf_redirector

def test_pdf_redirector():
    """测试PDF重定向器"""
    redirector = get_pdf_redirector()
    
    # 测试用例
    test_cases = [
        "https://arxiv.org/pdf/2301.00001.pdf",
        "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=12345",
        "https://dl.acm.org/doi/pdf/10.1145/12345",
        "https://link.springer.com/content/pdf/10.1007/s12345.pdf",
        "https://www.nature.com/articles/nature12345.pdf",
        "https://example.com/normal-url.html"  # 不应该重定向
    ]
    
    print("🧪 测试PDF重定向器")
    print("=" * 50)
    
    for url in test_cases:
        print(f"\n📝 测试URL: {url}")
        redirect_info = redirector.check_redirect(url)
        
        if redirect_info:
            print(f"✅ 重定向匹配!")
            print(f"   原始URL: {redirect_info['original_url']}")
            print(f"   标准URL: {redirect_info['canonical_url']}")
            print(f"   重定向原因: {redirect_info['redirect_reason']}")
            print(f"   规则名称: {redirect_info['rule_name']}")
        else:
            print("❌ 无需重定向")
    
    print("\n" + "=" * 50)
    print("🎯 支持的域名:")
    for domain in redirector.get_supported_domains():
        print(f"   - {domain}")

if __name__ == "__main__":
    test_pdf_redirector()
