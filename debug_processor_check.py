#!/usr/bin/env python3
"""
调试处理器可用性检查
测试为什么 Site Parser V2 不能处理 bioinf.jku.at 的PDF URL
"""

# 简化版本：直接测试逻辑，不导入复杂的依赖

def test_processor_logic():
    """测试处理器的can_handle逻辑"""
    
    # 测试URL
    test_url = "https://www.bioinf.jku.at/publications/older/2604.pdf"
    
    # SITE_RULES（从源码复制）
    SITE_RULES = {
        'proceedings.neurips.cc': {},
        'papers.nips.cc': {},
        'dl.acm.org': {},
        'ieeexplore.ieee.org': {},
        'openaccess.thecvf.com': {},
        'cv-foundation.org': {},
        'proceedings.mlr.press': {},
        'mlr.press': {},
        'bioinf.jku.at': {},
        'jku.at': {},
        'nature.com': {},
    }
    
    print(f"🧪 测试Site Parser V2处理器逻辑")
    print(f"URL: {test_url}")
    print()
    
    # 检查各个条件
    print("🔍 详细检查:")
    print(f"  ✅ URL存在: {bool(test_url)}")
    
    url_lower = test_url.lower()
    print(f"  📝 URL小写: {url_lower}")
    
    # 检查支持的站点
    print(f"  📋 SITE_RULES包含的站点:")
    for site in SITE_RULES.keys():
        in_url = site in url_lower
        print(f"    - {site}: {'✅' if in_url else '❌'} {'(匹配)' if in_url else ''}")
    
    is_supported = any(site in url_lower for site in SITE_RULES.keys())
    print(f"  🎯 支持的站点: {is_supported}")
    
    is_pdf = url_lower.endswith('.pdf')
    print(f"  📄 是PDF文件: {is_pdf}")
    
    can_handle_result = is_supported and not is_pdf
    print(f"  🎪 最终结果 (支持 AND NOT PDF): {can_handle_result}")
    
    print()
    if can_handle_result:
        print("🎉 处理器可以处理此URL")
    else:
        print("❌ 处理器无法处理此URL")
        if is_pdf:
            print("💡 原因: 当前Site Parser V2过滤掉了PDF文件")
            print("💡 建议: 考虑为PDF添加专门的处理逻辑")
            print("💡 解决方案: 要么修改Site Parser V2支持PDF，要么添加PDF专门处理器")

if __name__ == "__main__":
    test_processor_logic()
