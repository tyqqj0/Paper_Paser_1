"""
IEEE适配器

处理IEEE Xplore网站的URL映射。
"""

import re
import logging
from typing import List, Dict, Any, Optional

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy
from ..strategies.scraping_strategy import ScrapingStrategy
from ..strategies.database_strategy import DatabaseStrategy
from ..extractors.ieee_extractor import IEEEExtractor

logger = logging.getLogger(__name__)


# IEEE特定的处理函数
async def process_ieee_match(match: re.Match, result: URLMappingResult,
                           pattern_name: str, url: str, context: Dict[str, Any]):
    """处理IEEE URL匹配结果"""
    document_id = match.group(1)
    result.source_page_url = url
    result.venue = "IEEE"
    result.confidence = 0.7  # 中等置信度，因为还需要进一步解析获取DOI
    
    # 将文档ID存储在identifiers中，供后续策略使用
    result.identifiers["ieee_document_id"] = document_id
    
    logger.debug(f"IEEE正则匹配成功，文档ID: {document_id}")


async def ieee_scraping_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """IEEE页面解析函数 - 提取真实DOI"""
    return IEEEExtractor.extract_from_page(url)


async def ieee_semantic_scholar_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """IEEE Semantic Scholar查询函数"""
    return IEEEExtractor.extract_from_semantic_scholar(url)


class IEEEAdapter(URLAdapter):
    """IEEE适配器 - 处理IEEE Xplore网站"""

    @property
    def name(self) -> str:
        return "ieee"

    @property
    def supported_domains(self) -> List[str]:
        return ["ieeexplore.ieee.org"]

    def can_handle(self, url: str) -> bool:
        return "ieeexplore.ieee.org" in url.lower()

    def _register_strategies(self):
        """注册IEEE支持的策略"""
        
        # IEEE正则策略 - 提取文档ID
        ieee_patterns = {
            "document_id": r"ieeexplore\.ieee\.org/(?:document|abstract/document)/(\d+)",
        }

        self.strategies = [
            # 策略1: 正则表达式提取文档ID（优先级最高，速度最快）
            RegexStrategy("ieee_regex", ieee_patterns, process_ieee_match, priority=1),
            
            # 策略2: 页面解析提取DOI（优先级中等，准确度高）
            ScrapingStrategy("ieee_scraping", ieee_scraping_func, priority=2),
            
            # 策略3: Semantic Scholar查询（优先级最低，作为备选）
            DatabaseStrategy("ieee_semantic_scholar", ieee_semantic_scholar_func, priority=3),
            
            # 未来可以添加更多策略：
            # APIStrategy("ieee_api", ieee_api_func, priority=2),
            # DatabaseStrategy("ieee_crossref", crossref_func, priority=4),
        ]

    def _get_context(self) -> Dict[str, Any]:
        """获取IEEE特定的上下文信息"""
        context = super()._get_context()
        context.update({
            "ieee_specific": True,
            "requires_scraping": True,
            "supports_document_id": True,
        })
        return context

    def extract_document_id(self, url: str) -> Optional[str]:
        """
        从IEEE URL中提取文档ID
        
        Args:
            url: IEEE URL
            
        Returns:
            文档ID，如果没有找到则返回None
        """
        return IEEEExtractor.extract_document_id(url)

    def is_ieee_url(self, url: str) -> bool:
        """
        检查URL是否为IEEE URL
        
        Args:
            url: 要检查的URL
            
        Returns:
            是否为IEEE URL
        """
        return self.can_handle(url)

    def get_ieee_document_url(self, document_id: str) -> str:
        """
        根据文档ID构建IEEE文档URL
        
        Args:
            document_id: IEEE文档ID
            
        Returns:
            IEEE文档URL
        """
        return f"https://ieeexplore.ieee.org/document/{document_id}"

    async def extract_with_fallback(self, url: str) -> URLMappingResult:
        """
        使用备选方案提取信息
        
        这个方法提供了一个更灵活的提取接口，
        会尝试所有可用的策略并返回最佳结果。
        
        Args:
            url: IEEE URL
            
        Returns:
            提取结果
        """
        logger.info(f"开始IEEE备选提取: {url}")
        
        # 首先尝试标准的多策略提取
        result = await self.extract_identifiers(url)
        
        if result.is_successful():
            logger.info(f"IEEE标准提取成功: DOI={result.doi}")
            return result
        
        # 如果标准提取失败，尝试更多的备选方案
        logger.info("IEEE标准提取失败，尝试备选方案")
        
        # 备选方案1: 直接使用IEEE提取器
        try:
            fallback_result = IEEEExtractor.extract_from_page(url)
            if fallback_result and fallback_result.is_successful():
                fallback_result.source_adapter = self.name
                fallback_result.strategy_used = "ieee_fallback_extractor"
                logger.info(f"IEEE备选提取成功: DOI={fallback_result.doi}")
                return fallback_result
        except Exception as e:
            logger.warning(f"IEEE备选提取失败: {e}")
        
        # 如果所有方法都失败，返回基本信息
        logger.warning("IEEE所有提取方法都失败，返回基本信息")
        basic_result = URLMappingResult()
        basic_result.source_page_url = url
        basic_result.venue = "IEEE"
        basic_result.source_adapter = self.name
        basic_result.strategy_used = "ieee_basic_fallback"
        basic_result.confidence = 0.3  # 低置信度
        
        # 尝试提取文档ID
        doc_id = self.extract_document_id(url)
        if doc_id:
            basic_result.identifiers["ieee_document_id"] = doc_id
        
        return basic_result
