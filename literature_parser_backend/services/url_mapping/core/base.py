"""
URL映射基类定义

包含适配器和策略的抽象基类。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from .result import URLMappingResult

logger = logging.getLogger(__name__)


class IdentifierStrategy(ABC):
    """标识符提取策略接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级，数字越小优先级越高"""
        pass

    @abstractmethod
    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """
        从URL提取标识符

        Args:
            url: 要解析的URL
            context: 上下文信息，包含平台特定的配置和状态

        Returns:
            URLMappingResult或None
        """
        pass

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断策略是否可以处理该URL
        默认返回True，子类可以重写以添加特定条件
        """
        return True


class URLAdapter(ABC):
    """URL适配器基类 - 支持多策略的增强版本"""

    def __init__(self):
        self.strategies: List[IdentifierStrategy] = []
        self._register_strategies()

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称"""
        pass

    @property
    @abstractmethod
    def supported_domains(self) -> List[str]:
        """支持的域名列表"""
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断适配器是否可以处理该URL"""
        pass

    @abstractmethod
    def _register_strategies(self):
        """注册该适配器支持的策略"""
        pass

    def _get_context(self) -> Dict[str, Any]:
        """获取适配器特定的上下文信息"""
        return {
            "adapter_name": self.name,
            "supported_domains": self.supported_domains,
        }

    async def extract_identifiers(self, url: str, enable_validation: bool = False, strict_validation: bool = False) -> URLMappingResult:
        """
        使用多策略瀑布流提取标识符
        按优先级尝试各种策略，直到成功或全部失败

        Args:
            url: 要处理的URL
            enable_validation: 是否启用标识符验证
            strict_validation: 是否使用严格验证模式（验证失败时不返回结果）
        """
        logger.debug(f"开始使用 {self.name} 适配器处理URL: {url}")

        context = self._get_context()
        context.update({
            'enable_doi_validation': enable_validation,
            'enable_arxiv_validation': enable_validation,
            'strict_validation': strict_validation,
        })

        available_strategies = [
            s for s in self.strategies
            if s.can_handle(url, context)
        ]

        if not available_strategies:
            logger.warning(f"没有可用的策略处理URL: {url}")
            return URLMappingResult(source_adapter=self.name)

        # 按优先级排序并尝试每个策略
        best_result = None

        for strategy in sorted(available_strategies, key=lambda s: s.priority):
            try:
                logger.debug(f"尝试策略: {strategy.name} (优先级: {strategy.priority})")

                # 更新上下文中的当前结果（用于验证策略）
                context['current_result'] = best_result

                result = await strategy.extract_identifiers(url, context)

                if result:
                    # 检查是否有有效的标识符或有用信息
                    has_identifiers = result.has_identifiers()
                    has_useful_info = result.has_useful_info()

                    if has_identifiers or has_useful_info:
                        result.source_adapter = self.name
                        result.strategy_used = strategy.name

                        # 如果有标识符（DOI/ArXiv），立即返回
                        if has_identifiers:
                            logger.info(f"策略 {strategy.name} 成功提取标识符: DOI={result.doi}, ArXiv={result.arxiv_id}")
                            return result

                        # 如果只有有用信息，保存为备选结果，继续尝试其他策略
                        if not best_result:
                            best_result = result
                            logger.debug(f"策略 {strategy.name} 提取到有用信息，继续尝试获取标识符")
                    else:
                        logger.debug(f"策略 {strategy.name} 未找到有效标识符或有用信息")
                else:
                    logger.debug(f"策略 {strategy.name} 返回None")

            except Exception as e:
                logger.warning(f"策略 {strategy.name} 执行失败: {e}")
                continue

        # 如果没有找到标识符，返回最佳的有用信息结果
        if best_result:
            logger.info(f"返回最佳结果: {best_result.source_adapter} - {best_result.strategy_used}")
            return best_result

        # 如果所有策略都失败，返回空结果
        logger.debug(f"所有策略都失败，返回空结果")
        return URLMappingResult(source_adapter=self.name)
