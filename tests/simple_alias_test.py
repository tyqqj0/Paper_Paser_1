#!/usr/bin/env python3
"""
别名系统核心功能测试（无外部依赖版本）

这是一个独立的测试脚本，验证别名系统的核心逻辑。
"""

import asyncio
from enum import Enum
from typing import Dict, Any, Optional


class AliasType(str, Enum):
    """别名类型枚举"""
    DOI = "doi"
    ARXIV = "arxiv"
    URL = "url"
    PDF_URL = "pdf_url"
    PMID = "pmid"
    TITLE = "title"


def normalize_alias_value(alias_type: AliasType, alias_value: str) -> str:
    """别名值标准化"""
    if not alias_value:
        return alias_value
    
    value = alias_value.strip()
    
    if alias_type == AliasType.DOI:
        if value.startswith("https://doi.org/"):
            value = value[16:]
        elif value.startswith("http://doi.org/"):
            value = value[15:]
        elif value.startswith("doi:"):
            value = value[4:]
        return value.lower()
    
    elif alias_type == AliasType.ARXIV:
        if value.startswith("https://arxiv.org/abs/"):
            value = value[22:]
        elif value.startswith("arxiv:"):
            value = value[6:]
        return value.lower()
    
    elif alias_type in [AliasType.URL, AliasType.PDF_URL]:
        return value
    
    elif alias_type == AliasType.TITLE:
        return value.lower().strip()
    
    else:
        return value.lower().strip()


def extract_aliases_from_source(source_data: Dict[str, Any]) -> Dict[AliasType, str]:
    """从源数据提取别名映射"""
    aliases = {}
    
    if doi := source_data.get("doi"):
        aliases[AliasType.DOI] = normalize_alias_value(AliasType.DOI, doi)
    
    if arxiv_id := source_data.get("arxiv_id"):
        aliases[AliasType.ARXIV] = normalize_alias_value(AliasType.ARXIV, arxiv_id)
    
    if url := source_data.get("url"):
        aliases[AliasType.URL] = normalize_alias_value(AliasType.URL, url)
    
    if pdf_url := source_data.get("pdf_url"):
        aliases[AliasType.PDF_URL] = normalize_alias_value(AliasType.PDF_URL, pdf_url)
    
    if pmid := source_data.get("pmid"):
        aliases[AliasType.PMID] = normalize_alias_value(AliasType.PMID, pmid)
    
    if title := source_data.get("title"):
        aliases[AliasType.TITLE] = normalize_alias_value(AliasType.TITLE, title)
    
    return aliases


class MockAliasDAO:
    """模拟别名DAO，用于测试"""
    
    def __init__(self):
        self.storage = {}  # {alias_key: lid}
    
    def _make_key(self, alias_type: AliasType, alias_value: str) -> str:
        normalized_value = normalize_alias_value(alias_type, alias_value)
        return f"{alias_type.value}:{normalized_value}"
    
    async def create_mapping(self, alias_type: AliasType, alias_value: str, lid: str) -> str:
        """创建别名映射"""
        key = self._make_key(alias_type, alias_value)
        
        if key in self.storage:
            if self.storage[key] == lid:
                return "existing_mapping"
            else:
                raise ValueError(f"Conflicting mapping: {key} already maps to {self.storage[key]}, tried to map to {lid}")
        
        self.storage[key] = lid
        return f"mapping_{len(self.storage)}"
    
    async def lookup_alias(self, alias_type: AliasType, alias_value: str) -> Optional[str]:
        """查找别名映射"""
        key = self._make_key(alias_type, alias_value)
        return self.storage.get(key)
    
    async def resolve_to_lid(self, source_data: Dict[str, Any]) -> Optional[str]:
        """将源数据解析为LID"""
        aliases = extract_aliases_from_source(source_data)
        
        for alias_type, alias_value in aliases.items():
            lid = await self.lookup_alias(alias_type, alias_value)
            if lid:
                return lid
        
        return None
    
    async def batch_create_mappings(self, lid: str, mappings: Dict[AliasType, str]) -> list:
        """批量创建别名映射"""
        created_ids = []
        
        for alias_type, alias_value in mappings.items():
            if alias_value:  # 跳过空值
                try:
                    mapping_id = await self.create_mapping(alias_type, alias_value, lid)
                    created_ids.append(mapping_id)
                except Exception as e:
                    print(f"警告：创建映射失败 {alias_type}={alias_value}: {e}")
        
        return created_ids
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        type_counts = {}
        for key in self.storage.keys():
            alias_type = key.split(':', 1)[0]
            type_counts[alias_type] = type_counts.get(alias_type, 0) + 1
        
        return {
            "total_mappings": len(self.storage),
            "mappings_by_type": type_counts,
            "all_mappings": dict(self.storage)
        }


async def test_basic_functionality():
    """测试基础功能"""
    print("=== 测试基础功能 ===")
    
    dao = MockAliasDAO()
    
    # 测试创建映射
    await dao.create_mapping(AliasType.DOI, "10.1038/nature12345", "2023-smith-paper-a1b2")
    await dao.create_mapping(AliasType.ARXIV, "1706.03762", "2017-vaswani-aiaynu-c3d4")
    await dao.create_mapping(AliasType.URL, "https://example.com/paper", "2023-smith-paper-a1b2")
    
    print("✓ 创建了3个别名映射")
    
    # 测试查找
    lid1 = await dao.lookup_alias(AliasType.DOI, "10.1038/nature12345")
    lid2 = await dao.lookup_alias(AliasType.DOI, "https://doi.org/10.1038/nature12345")  # 应该标准化后找到
    lid3 = await dao.lookup_alias(AliasType.DOI, "10.1000/nonexistent")  # 不应该找到
    
    print(f"DOI查找结果: {lid1}")
    print(f"DOI URL查找结果: {lid2}")
    print(f"不存在DOI查找结果: {lid3}")
    
    assert lid1 == "2023-smith-paper-a1b2"
    assert lid2 == "2023-smith-paper-a1b2"  # 标准化后应该找到相同结果
    assert lid3 is None
    
    print("✓ 基础功能测试通过\n")


async def test_source_resolution():
    """测试源数据解析"""
    print("=== 测试源数据解析 ===")
    
    dao = MockAliasDAO()
    
    # 先创建一些映射
    await dao.create_mapping(AliasType.DOI, "10.1038/nature12345", "nature-paper-lid")
    await dao.create_mapping(AliasType.ARXIV, "1706.03762", "transformer-paper-lid")
    
    # 测试解析
    test_cases = [
        ({"doi": "10.1038/nature12345"}, "nature-paper-lid"),
        ({"doi": "https://doi.org/10.1038/nature12345"}, "nature-paper-lid"),  # 标准化
        ({"arxiv_id": "1706.03762"}, "transformer-paper-lid"),
        ({"url": "https://unknown-site.com"}, None),  # 未知URL
        ({}, None),  # 空数据
    ]
    
    for source_data, expected_lid in test_cases:
        result = await dao.resolve_to_lid(source_data)
        status = "✓" if result == expected_lid else "✗"
        print(f"{status} 源数据 {source_data} -> {result} (期望: {expected_lid})")
    
    print("✓ 源数据解析测试完成\n")


async def test_batch_operations():
    """测试批量操作"""
    print("=== 测试批量操作 ===")
    
    dao = MockAliasDAO()
    
    # 批量创建映射
    mappings = {
        AliasType.DOI: "10.1038/nature12345",
        AliasType.ARXIV: "1706.03762", 
        AliasType.URL: "https://example.com/paper",
        AliasType.PDF_URL: "https://example.com/paper.pdf",
        AliasType.TITLE: "Some Research Paper"
    }
    
    created_ids = await dao.batch_create_mappings("batch-test-lid", mappings)
    
    print(f"批量创建了 {len(created_ids)} 个映射")
    
    # 验证所有映射都能找到
    for alias_type, alias_value in mappings.items():
        found_lid = await dao.lookup_alias(alias_type, alias_value)
        assert found_lid == "batch-test-lid"
    
    print("✓ 批量操作测试通过\n")


async def test_workflow_scenarios():
    """测试完整工作流程场景"""
    print("=== 测试工作流程场景 ===")
    
    dao = MockAliasDAO()
    
    print("场景1: 用户首次提交DOI")
    source_1 = {"doi": "10.1038/nature12345", "title": "Nature Paper"}
    lid_1 = await dao.resolve_to_lid(source_1)
    print(f"  别名解析结果: {lid_1}")
    assert lid_1 is None  # 首次提交应该找不到
    
    # 模拟任务完成，创建映射
    aliases_1 = extract_aliases_from_source(source_1)
    await dao.batch_create_mappings("nature-paper-lid", aliases_1)
    print(f"  任务完成，创建了 {len(aliases_1)} 个映射")
    
    print("\n场景2: 相同DOI再次提交")
    lid_2 = await dao.resolve_to_lid(source_1)
    print(f"  别名解析结果: {lid_2}")
    assert lid_2 == "nature-paper-lid"  # 应该立即找到
    
    print("\n场景3: 不同标识符提交相同文献")
    source_3 = {"url": "https://nature.com/articles/nature12345"}
    lid_3 = await dao.resolve_to_lid(source_3)
    print(f"  别名解析结果: {lid_3}")
    assert lid_3 is None  # URL未记录，应该找不到
    
    # 模拟去重发现现有文献，记录新映射
    aliases_3 = extract_aliases_from_source(source_3)
    await dao.batch_create_mappings("nature-paper-lid", aliases_3)
    print(f"  去重发现现有文献，记录了 {len(aliases_3)} 个新映射")
    
    print("\n场景4: 用新URL再次提交")
    lid_4 = await dao.resolve_to_lid(source_3)
    print(f"  别名解析结果: {lid_4}")
    assert lid_4 == "nature-paper-lid"  # 新URL映射应该被找到
    
    print("✓ 工作流程场景测试通过\n")


async def test_edge_cases():
    """测试边缘情况"""
    print("=== 测试边缘情况 ===")
    
    dao = MockAliasDAO()
    
    # 测试空值处理
    empty_aliases = extract_aliases_from_source({})
    print(f"空源数据提取别名: {len(empty_aliases)}")
    
    # 测试None值和空字符串
    partial_data = {
        "doi": None,
        "url": "",
        "title": "   ",  # 只有空格
        "arxiv_id": "1234.5678"  # 只有这个有效
    }
    
    partial_aliases = extract_aliases_from_source(partial_data)
    print(f"部分有效数据提取别名: {len(partial_aliases)}")
    print(f"提取的别名类型: {list(partial_aliases.keys())}")
    
    # 测试标准化
    test_normalizations = [
        (AliasType.DOI, "https://doi.org/10.1038/NATURE12345", "10.1038/nature12345"),
        (AliasType.ARXIV, "https://arxiv.org/abs/1706.03762v1", "1706.03762v1"),
        (AliasType.TITLE, "  THE PAPER TITLE  ", "the paper title"),
    ]
    
    print("标准化测试:")
    for alias_type, input_val, expected in test_normalizations:
        result = normalize_alias_value(alias_type, input_val)
        status = "✓" if result == expected else "✗"
        print(f"  {status} {alias_type.value}: '{input_val}' -> '{result}'")
    
    print("✓ 边缘情况测试完成\n")


async def run_all_tests():
    """运行所有测试"""
    print("🧪 别名系统核心功能测试\n")
    
    try:
        await test_basic_functionality()
        await test_source_resolution()
        await test_batch_operations()
        await test_workflow_scenarios()
        await test_edge_cases()
        
        print("🎉 所有测试通过！别名系统核心功能正常。")
        
        # 显示最终统计
        dao = MockAliasDAO()
        
        # 创建一些示例数据来展示统计
        await dao.create_mapping(AliasType.DOI, "10.1038/nature1", "paper-1")
        await dao.create_mapping(AliasType.ARXIV, "1706.1", "paper-2") 
        await dao.create_mapping(AliasType.URL, "https://example.com/1", "paper-1")
        
        stats = dao.get_stats()
        print(f"\n📊 别名系统统计:")
        print(f"总映射数: {stats['total_mappings']}")
        print(f"按类型分布: {stats['mappings_by_type']}")
        
        print("\n✅ 测试总结:")
        print("✓ 别名创建和查找")
        print("✓ 源数据解析到LID")
        print("✓ 批量映射操作")
        print("✓ 完整工作流程")
        print("✓ 边缘情况处理")
        print("✓ 值标准化功能")
        
    except AssertionError as e:
        print(f"❌ 测试失败: {e}")
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
