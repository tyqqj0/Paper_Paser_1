"""
正则表达式策略

基于正则表达式模式匹配的标识符提取策略。
"""

import re
import logging
from typing import Dict, Optional, Any, Callable

from ..core.base import IdentifierStrategy
from ..core.result import URLMappingResult

logger = logging.getLogger(__name__)


class RegexStrategy(IdentifierStrategy):
    """基于正则表达式的标识符提取策略"""

    def __init__(self, name: str, patterns: Dict[str, str], processor_func: Optional[Callable] = None, priority: int = 1):
        """
        初始化正则策略
        
        Args:
            name: 策略名称
            patterns: 正则表达式模式字典 {模式名: 正则表达式}
            processor_func: 自定义处理函数
            priority: 优先级
        """
        self._name = name
        self.patterns = patterns
        self.processor_func = processor_func
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """使用正则表达式提取标识符"""
        result = URLMappingResult()

        for pattern_name, pattern in self.patterns.items():
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                logger.debug(f"正则模式 {pattern_name} 匹配成功")

                # 使用自定义处理函数或默认处理
                if self.processor_func:
                    await self.processor_func(match, result, pattern_name, url, context)
                else:
                    await self._default_process_match(match, result, pattern_name, url, context)
                break

        # 返回结果的条件：有标识符或有其他有用信息
        return result if result.is_successful() else None

    async def _default_process_match(self, match: re.Match, result: URLMappingResult, 
                                   pattern_name: str, url: str, context: Dict[str, Any]):
        """
        默认的匹配处理逻辑
        
        Args:
            match: 正则匹配结果
            result: 要填充的结果对象
            pattern_name: 模式名称
            url: 原始URL
            context: 上下文信息
        """
        # 默认处理：尝试从第一个捕获组提取标识符
        if match.groups():
            identifier = match.group(1)
            
            # 根据模式名称判断标识符类型
            if 'doi' in pattern_name.lower():
                result.doi = identifier
            elif 'arxiv' in pattern_name.lower():
                result.arxiv_id = identifier
            elif 'pmid' in pattern_name.lower():
                result.pmid = identifier
            else:
                # 默认存储在identifiers字典中
                result.identifiers[pattern_name] = identifier
            
            result.source_page_url = url
            result.confidence = 0.8  # 默认置信度
            
            logger.debug(f"默认处理提取到标识符: {pattern_name}={identifier}")

    def add_pattern(self, pattern_name: str, pattern: str):
        """
        添加新的正则表达式模式
        
        Args:
            pattern_name: 模式名称
            pattern: 正则表达式
        """
        self.patterns[pattern_name] = pattern
        logger.debug(f"添加正则模式: {pattern_name}")

    def remove_pattern(self, pattern_name: str):
        """
        移除正则表达式模式
        
        Args:
            pattern_name: 要移除的模式名称
        """
        if pattern_name in self.patterns:
            del self.patterns[pattern_name]
            logger.debug(f"移除正则模式: {pattern_name}")

    def get_patterns(self) -> Dict[str, str]:
        """
        获取所有正则表达式模式
        
        Returns:
            模式字典的副本
        """
        return self.patterns.copy()
