"""
执行条件检查器 - 统一的前置和后置条件检查
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RequirementLevel(Enum):
    """需求级别"""
    REQUIRED = "required"      # 必需：缺失则跳过执行
    PREFERRED = "preferred"    # 偏好：缺失则降级执行
    OPTIONAL = "optional"      # 可选：缺失仅记录警告


@dataclass
class RequirementItem:
    """单个需求项"""
    name: str                          # 需求名称
    level: RequirementLevel           # 需求级别
    check_path: str                   # 检查路径，如 "metadata.identifiers.doi"
    alternatives: Optional[List[str]] = None  # 替代路径
    validator: Optional[callable] = None      # 自定义验证函数
    
    def check_value(self, context: Dict[str, Any]) -> tuple[bool, Any]:
        """检查值是否存在且有效"""
        # 主路径检查
        value = self._get_nested_value(context, self.check_path)
        if self._is_valid_value(value):
            return True, value
            
        # 替代路径检查
        if self.alternatives:
            for alt_path in self.alternatives:
                alt_value = self._get_nested_value(context, alt_path)
                if self._is_valid_value(alt_value):
                    return True, alt_value
                    
        return False, None
    
    def _get_nested_value(self, context: Dict[str, Any], path: str) -> Any:
        """获取嵌套路径的值"""
        try:
            obj = context
            for key in path.split('.'):
                if hasattr(obj, key):
                    obj = getattr(obj, key)
                elif isinstance(obj, dict) and key in obj:
                    obj = obj[key]
                else:
                    return None
            return obj
        except:
            return None
    
    def _is_valid_value(self, value: Any) -> bool:
        """检查值是否有效"""
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False
            
        # 自定义验证器
        if self.validator:
            return self.validator(value)
            
        return True


@dataclass 
class CheckResult:
    """检查结果"""
    passed: bool                      # 是否通过
    execution_mode: str              # 执行模式：'normal', 'degraded', 'skip'
    missing_required: List[str]      # 缺失的必需项
    missing_preferred: List[str]     # 缺失的偏好项
    missing_optional: List[str]      # 缺失的可选项
    available_data: Dict[str, Any]   # 可用的数据
    reason: str = ""                 # 详细原因


class RequirementChecker:
    """需求检查器基类"""
    
    def __init__(self, requirements: List[RequirementItem]):
        self.requirements = requirements
    
    def check_preconditions(self, context: Dict[str, Any]) -> CheckResult:
        """检查前置条件"""
        missing_required = []
        missing_preferred = []
        missing_optional = []
        available_data = {}
        
        for req in self.requirements:
            passed, value = req.check_value(context)
            
            if passed:
                available_data[req.name] = value
            else:
                if req.level == RequirementLevel.REQUIRED:
                    missing_required.append(req.name)
                elif req.level == RequirementLevel.PREFERRED:
                    missing_preferred.append(req.name)
                else:  # OPTIONAL
                    missing_optional.append(req.name)
        
        # 决定执行模式
        if missing_required:
            execution_mode = 'skip'
            passed = False
            reason = f"Missing required items: {', '.join(missing_required)}"
        elif missing_preferred:
            execution_mode = 'degraded'  
            passed = True
            reason = f"Missing preferred items: {', '.join(missing_preferred)}"
        else:
            execution_mode = 'normal'
            passed = True
            reason = "All requirements satisfied"
        
        return CheckResult(
            passed=passed,
            execution_mode=execution_mode,
            missing_required=missing_required,
            missing_preferred=missing_preferred,
            missing_optional=missing_optional,
            available_data=available_data,
            reason=reason
        )


# =================== 具体的检查器实现 ===================

class ReferencesFetchRequirementChecker(RequirementChecker):
    """引用获取需求检查器"""
    
    def __init__(self):
        requirements = [
            RequirementItem(
                name="doi",
                level=RequirementLevel.PREFERRED,
                check_path="metadata.identifiers.doi",
                alternatives=["metadata.doi"]
            ),
            RequirementItem(
                name="arxiv_id", 
                level=RequirementLevel.PREFERRED,
                check_path="metadata.identifiers.arxiv_id",
                alternatives=["metadata.arxiv_id"]
            ),
            RequirementItem(
                name="literature_id",
                level=RequirementLevel.REQUIRED,
                check_path="literature_id"
            ),
            RequirementItem(
                name="title",
                level=RequirementLevel.OPTIONAL,
                check_path="metadata.title",
                validator=lambda x: len(x.strip()) > 5 if isinstance(x, str) else False
            )
        ]
        super().__init__(requirements)
    
    def check_preconditions(self, context: Dict[str, Any]) -> CheckResult:
        """重写检查逻辑，添加特殊规则"""
        result = super().check_preconditions(context)
        
        # 特殊规则：DOI和ArXiv ID至少要有一个
        has_doi = 'doi' in result.available_data
        has_arxiv = 'arxiv_id' in result.available_data
        
        if not has_doi and not has_arxiv:
            result.passed = False
            result.execution_mode = 'skip'
            result.reason = "Neither DOI nor ArXiv ID available - cannot fetch references"
            result.missing_required.append("doi_or_arxiv_id")
        
        return result


class CitationResolverRequirementChecker(RequirementChecker):
    """引用解析需求检查器"""
    
    def __init__(self):
        requirements = [
            RequirementItem(
                name="references",
                level=RequirementLevel.REQUIRED,
                check_path="references",
                validator=lambda x: isinstance(x, list) and len(x) > 0
            ),
            RequirementItem(
                name="literature_id",
                level=RequirementLevel.REQUIRED,
                check_path="literature_id"
            )
        ]
        super().__init__(requirements)


# =================== 工厂方法 ===================

def create_requirement_checker(hook_name: str) -> RequirementChecker:
    """根据Hook名称创建对应的需求检查器"""
    checkers = {
        'references_fetch': ReferencesFetchRequirementChecker,
        'citation_resolver': CitationResolverRequirementChecker,
    }
    
    checker_class = checkers.get(hook_name)
    if not checker_class:
        # 返回空检查器（总是通过）
        return RequirementChecker([])
    
    return checker_class()



