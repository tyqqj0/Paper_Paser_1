#!/usr/bin/env python3
"""
标识符需求分类系统 - 支持必须/可选/非必须的灵活处理策略

设计理念：
1. 必须标识符(REQUIRED)：缺少时任务失败
2. 可选标识符(OPTIONAL)：缺少时继续处理但记录警告
3. 非必须标识符(NICE_TO_HAVE)：缺少时正常处理，仅用于增强功能

这解决了像MLR Press这样没有DOI但有价值的论文被错误跳过的问题。
"""

from enum import Enum
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from loguru import logger


class IdentifierRequirement(Enum):
    """标识符需求级别"""
    REQUIRED = "required"           # 必须有，缺少时任务失败
    OPTIONAL = "optional"           # 可选，缺少时继续但记录
    NICE_TO_HAVE = "nice_to_have"   # 非必须，仅用于增强功能


class ComponentType(Enum):
    """系统组件类型"""
    METADATA_FETCH = "metadata_fetch"       # 元数据获取
    REFERENCE_FETCH = "reference_fetch"     # 参考文献获取  
    DEDUPLICATION = "deduplication"         # 去重检查
    CITATION_ANALYSIS = "citation_analysis" # 引用分析
    FULL_TEXT_PARSE = "full_text_parse"     # 全文解析


@dataclass
class IdentifierRequirementConfig:
    """标识符需求配置"""
    component: ComponentType
    required_identifiers: Set[str]      # 必须有的标识符
    optional_identifiers: Set[str]      # 可选的标识符
    nice_to_have_identifiers: Set[str]  # 非必须的标识符
    fallback_strategy: str              # 缺少标识符时的回退策略
    
    def get_requirement_level(self, identifier_type: str) -> IdentifierRequirement:
        """获取特定标识符的需求级别"""
        if identifier_type in self.required_identifiers:
            return IdentifierRequirement.REQUIRED
        elif identifier_type in self.optional_identifiers:
            return IdentifierRequirement.OPTIONAL
        elif identifier_type in self.nice_to_have_identifiers:
            return IdentifierRequirement.NICE_TO_HAVE
        else:
            return IdentifierRequirement.NICE_TO_HAVE  # 默认非必须


class IdentifierRequirementManager:
    """标识符需求管理器"""
    
    def __init__(self):
        """初始化默认配置"""
        self.configs: Dict[ComponentType, IdentifierRequirementConfig] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """设置默认的标识符需求配置"""
        
        # 元数据获取：基本不需要特定标识符（可以从URL等获取）
        self.configs[ComponentType.METADATA_FETCH] = IdentifierRequirementConfig(
            component=ComponentType.METADATA_FETCH,
            required_identifiers=set(),  # 没有必须的标识符
            optional_identifiers={"doi", "arxiv_id", "pmid"},  # DOI等可选
            nice_to_have_identifiers={"url", "pdf_url", "semantic_scholar_id"},
            fallback_strategy="continue_with_url_parsing"
        )
        
        # 参考文献获取：DOI优先，但ArXiv也可以，都没有时尝试其他方法
        self.configs[ComponentType.REFERENCE_FETCH] = IdentifierRequirementConfig(
            component=ComponentType.REFERENCE_FETCH,
            required_identifiers=set(),  # 🆕 不再硬性要求DOI
            optional_identifiers={"doi", "arxiv_id"},  # DOI和ArXiv都是可选的
            nice_to_have_identifiers={"pmid", "semantic_scholar_id", "url"},
            fallback_strategy="try_alternative_methods"  # 🆕 尝试其他方法
        )
        
        # 去重检查：任何标识符都有助于去重
        self.configs[ComponentType.DEDUPLICATION] = IdentifierRequirementConfig(
            component=ComponentType.DEDUPLICATION,
            required_identifiers=set(),
            optional_identifiers={"doi", "arxiv_id", "pmid"},
            nice_to_have_identifiers={"url", "pdf_url", "semantic_scholar_id"},
            fallback_strategy="use_content_fingerprint"
        )
        
        # 引用分析：需要稳定的标识符
        self.configs[ComponentType.CITATION_ANALYSIS] = IdentifierRequirementConfig(
            component=ComponentType.CITATION_ANALYSIS,
            required_identifiers=set(),
            optional_identifiers={"doi", "arxiv_id"},
            nice_to_have_identifiers={"pmid", "semantic_scholar_id"},
            fallback_strategy="skip_citation_analysis"
        )
        
        # 全文解析：主要依赖PDF或URL
        self.configs[ComponentType.FULL_TEXT_PARSE] = IdentifierRequirementConfig(
            component=ComponentType.FULL_TEXT_PARSE,
            required_identifiers=set(),
            optional_identifiers={"pdf_url", "url"},
            nice_to_have_identifiers={"doi", "arxiv_id"},
            fallback_strategy="extract_from_metadata"
        )
    
    def check_requirements(
        self, 
        component: ComponentType, 
        available_identifiers: Dict[str, str]
    ) -> 'RequirementCheckResult':
        """
        检查标识符需求是否满足
        
        Args:
            component: 要检查的组件类型
            available_identifiers: 可用的标识符字典 {type: value}
            
        Returns:
            RequirementCheckResult: 检查结果
        """
        config = self.configs.get(component)
        if not config:
            logger.warning(f"未找到组件 {component} 的标识符需求配置")
            return RequirementCheckResult(
                can_proceed=True,
                status="unknown_component",
                missing_required=[],
                missing_optional=[],
                available_identifiers=available_identifiers,
                fallback_strategy="continue_anyway"
            )
        
        # 过滤掉空值的标识符
        valid_identifiers = {
            k: v for k, v in available_identifiers.items() 
            if v is not None and str(v).strip()
        }
        
        available_types = set(valid_identifiers.keys())
        
        # 检查必须的标识符
        missing_required = config.required_identifiers - available_types
        
        # 检查可选的标识符
        missing_optional = config.optional_identifiers - available_types
        
        # 确定是否可以继续
        can_proceed = len(missing_required) == 0
        
        # 确定状态
        if len(missing_required) > 0:
            status = "missing_required"
        elif len(missing_optional) == len(config.optional_identifiers):
            status = "missing_all_optional"
        elif len(missing_optional) > 0:
            status = "missing_some_optional"
        else:
            status = "all_satisfied"
        
        return RequirementCheckResult(
            can_proceed=can_proceed,
            status=status,
            missing_required=list(missing_required),
            missing_optional=list(missing_optional),
            available_identifiers=valid_identifiers,
            fallback_strategy=config.fallback_strategy if not can_proceed or missing_optional else None
        )
    
    def get_component_config(self, component: ComponentType) -> Optional[IdentifierRequirementConfig]:
        """获取组件的标识符需求配置"""
        return self.configs.get(component)
    
    def update_component_config(self, config: IdentifierRequirementConfig):
        """更新组件的标识符需求配置"""
        self.configs[config.component] = config
        logger.info(f"已更新组件 {config.component} 的标识符需求配置")


@dataclass
class RequirementCheckResult:
    """标识符需求检查结果"""
    can_proceed: bool                           # 是否可以继续处理
    status: str                                # 检查状态
    missing_required: List[str]                # 缺少的必须标识符
    missing_optional: List[str]                # 缺少的可选标识符
    available_identifiers: Dict[str, str]      # 可用的标识符
    fallback_strategy: Optional[str] = None    # 建议的回退策略
    
    @property
    def should_warn(self) -> bool:
        """是否应该记录警告"""
        return len(self.missing_optional) > 0 or self.status == "missing_all_optional"
    
    @property
    def should_fail(self) -> bool:
        """是否应该失败"""
        return not self.can_proceed
    
    def get_log_message(self, component: ComponentType, task_id: str = "") -> str:
        """获取日志消息"""
        prefix = f"Task {task_id}: " if task_id else ""
        
        if self.should_fail:
            return f"{prefix}❌ [{component.value}] 缺少必须标识符: {', '.join(self.missing_required)}"
        elif self.should_warn:
            return f"{prefix}⚠️ [{component.value}] 缺少可选标识符: {', '.join(self.missing_optional)}，将使用回退策略: {self.fallback_strategy}"
        else:
            return f"{prefix}✅ [{component.value}] 标识符需求满足，可用: {list(self.available_identifiers.keys())}"


# 全局实例
identifier_requirement_manager = IdentifierRequirementManager()


def check_identifier_requirements(
    component: ComponentType, 
    identifiers: Dict[str, str], 
    task_id: str = ""
) -> RequirementCheckResult:
    """
    便捷函数：检查标识符需求
    
    Args:
        component: 组件类型
        identifiers: 可用标识符
        task_id: 任务ID（用于日志）
        
    Returns:
        RequirementCheckResult: 检查结果
    """
    result = identifier_requirement_manager.check_requirements(component, identifiers)
    
    # 记录日志
    log_msg = result.get_log_message(component, task_id)
    if result.should_fail:
        logger.error(log_msg)
    elif result.should_warn:
        logger.warning(log_msg)
    else:
        logger.info(log_msg)
    
    return result


if __name__ == "__main__":
    # 测试示例
    print("🧪 测试标识符需求分类系统...")
    
    # 测试场景1：有DOI的论文
    test_identifiers_1 = {"doi": "10.1038/nature14539", "url": "https://www.nature.com/articles/nature14539"}
    result1 = check_identifier_requirements(ComponentType.REFERENCE_FETCH, test_identifiers_1, "test1")
    print(f"场景1结果: {result1.status}, 可继续: {result1.can_proceed}")
    
    # 测试场景2：MLR Press论文（无DOI）
    test_identifiers_2 = {"url": "https://proceedings.mlr.press/v15/glorot11a.html"}
    result2 = check_identifier_requirements(ComponentType.REFERENCE_FETCH, test_identifiers_2, "test2")
    print(f"场景2结果: {result2.status}, 可继续: {result2.can_proceed}")
    
    # 测试场景3：只有ArXiv ID
    test_identifiers_3 = {"arxiv_id": "1409.4842"}
    result3 = check_identifier_requirements(ComponentType.REFERENCE_FETCH, test_identifiers_3, "test3")
    print(f"场景3结果: {result3.status}, 可继续: {result3.can_proceed}")
    
    print("\n✅ 测试完成！")



