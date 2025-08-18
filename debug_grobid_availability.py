#!/usr/bin/env python3
"""
调试GROBID处理器的可用性问题
"""

import sys
import os
import tempfile

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 需要设置环境变量避免配置错误
os.environ.setdefault('LITERATURE_PARSER_BACKEND_DB_HOST', 'localhost')
os.environ.setdefault('LITERATURE_PARSER_BACKEND_DB_PORT', '27017')
os.environ.setdefault('LITERATURE_PARSER_BACKEND_DB_USER', 'test')
os.environ.setdefault('LITERATURE_PARSER_BACKEND_DB_PASS', 'test')
os.environ.setdefault('LITERATURE_PARSER_BACKEND_DB_BASE', 'test')

from literature_parser_backend.worker.metadata.base import IdentifierData
from literature_parser_backend.worker.metadata.registry import get_global_registry
from literature_parser_backend.worker.metadata.processors.grobid import GrobidProcessor

def test_grobid_availability():
    """测试GROBID处理器的可用性逻辑"""
    
    print("🔍 调试GROBID处理器可用性")
    print("=" * 60)
    
    # 1. 检查处理器注册
    registry = get_global_registry()
    all_processors = registry.list_processors()
    
    print(f"📋 已注册的处理器: {all_processors}")
    print(f"🎯 GROBID是否已注册: {'GROBID' in all_processors}")
    
    if 'GROBID' not in all_processors:
        print("❌ GROBID处理器未注册!")
        return False
    
    # 2. 创建GROBID处理器实例
    try:
        grobid_processor = registry.get_processor('GROBID')
        print(f"✅ GROBID处理器实例创建成功: {grobid_processor}")
        print(f"   - 名称: {grobid_processor.name}")
        print(f"   - 类型: {grobid_processor.processor_type}")
        print(f"   - 优先级: {grobid_processor.priority}")
    except Exception as e:
        print(f"❌ 创建GROBID处理器实例失败: {e}")
        return False
    
    # 3. 测试不同场景下的can_handle逻辑
    test_cases = [
        {
            "name": "PDF URL案例",
            "data": IdentifierData(
                url="https://www.bioinf.jku.at/publications/older/2604.pdf",
                pdf_url="https://www.bioinf.jku.at/publications/older/2604.pdf"
            )
        },
        {
            "name": "PDF文件路径案例",
            "data": IdentifierData(
                file_path="/tmp/test.pdf"
            )
        },
        {
            "name": "只有标题，无强标识符案例",
            "data": IdentifierData(
                title="Long Short-Term Memory",
                url="https://www.bioinf.jku.at/publications/older/2604.pdf"
            )
        },
        {
            "name": "有DOI的案例",
            "data": IdentifierData(
                title="Some Paper Title",
                doi="10.1000/test",
                url="https://example.com/paper.pdf"
            )
        },
        {
            "name": "通用回退案例（无特殊标识符）",
            "data": IdentifierData(
                url="https://example.com/some-page"
            )
        }
    ]
    
    print("\n🧪 测试GROBID的can_handle逻辑:")
    print("-" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        name = test_case["name"]
        data = test_case["data"]
        
        can_handle = grobid_processor.can_handle(data)
        
        print(f"{i}. {name}")
        print(f"   输入: URL={data.url}, PDF_URL={data.pdf_url}, DOI={data.doi}")
        print(f"        Title={data.title}, File={data.file_path}")
        print(f"   结果: {'✅ 可以处理' if can_handle else '❌ 不能处理'}")
        print()
    
    # 4. 测试当前失败案例的具体数据
    print("🎯 测试当前失败案例的具体标识符数据:")
    print("-" * 60)
    
    # 模拟当前测试案例的数据
    current_test_data = IdentifierData(
        url="https://www.bioinf.jku.at/publications/older/2604.pdf",
        pdf_url="https://www.bioinf.jku.at/publications/older/2604.pdf",
        title=None,
        doi=None,
        arxiv_id=None,
        pmid=None
    )
    
    can_handle_current = grobid_processor.can_handle(current_test_data)
    print(f"当前测试案例数据:")
    print(f"  URL: {current_test_data.url}")
    print(f"  PDF_URL: {current_test_data.pdf_url}")
    print(f"  GROBID可以处理: {'✅ 是' if can_handle_current else '❌ 否'}")
    
    # 5. 检查所有可用处理器
    print("\n📊 对当前案例的所有可用处理器:")
    print("-" * 60)
    
    available_processors = registry.get_available_processors(current_test_data)
    if available_processors:
        for processor in available_processors:
            print(f"  ✅ {processor.name} (优先级: {processor.priority})")
    else:
        print("  ❌ 没有可用的处理器!")
    
    return True

if __name__ == "__main__":
    try:
        test_grobid_availability()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


