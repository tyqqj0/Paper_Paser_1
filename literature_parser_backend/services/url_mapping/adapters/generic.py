"""
通用适配器

处理未知期刊的备选方案。
"""

import logging
from typing import List, Dict, Any, Optional

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.database_strategy import DatabaseStrategy
from ..extractors.doi_extractor import DOIExtractor
from ..extractors.page_parser import PageParser
from ....worker.execution.exceptions import URLNotFoundException, URLAccessFailedException

logger = logging.getLogger(__name__)


async def generic_doi_extraction_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """通用DOI提取函数 - 从任何URL中尝试提取DOI"""
    try:
        logger.info(f"尝试通用DOI提取: {url}")
        
        # 方法1: 从URL路径直接提取DOI
        doi = DOIExtractor.extract_from_url(url)
        if doi:
            logger.info(f"✅ 从URL路径提取到DOI: {doi}")
            
            result = URLMappingResult()
            result.doi = doi
            result.source_page_url = url
            result.venue = "Unknown"
            result.confidence = 0.7  # 中等置信度
            return result
        
        # 方法2: 尝试页面解析提取DOI
        fetch_result = PageParser.fetch_page_with_details(url)
        if fetch_result.success and fetch_result.content:
            doi = DOIExtractor.extract_from_content(fetch_result.content)
            if doi:
                logger.info(f"✅ 从页面内容提取到DOI: {doi}")
                
                result = URLMappingResult()
                result.doi = doi
                result.source_page_url = url
                result.venue = "Unknown"
                result.confidence = 0.8  # 较高置信度
                
                # 尝试提取标题
                title = PageParser.extract_title(fetch_result.content)
                if title:
                    result.title = title
                
                return result
        elif not fetch_result.success:
            # 记录具体的URL访问错误
            logger.warning(f"❌ 页面访问失败: {fetch_result.error_message} (错误类型: {fetch_result.error_type})")
            
            # 根据错误类型抛出特定的异常
            if fetch_result.error_type == "url_not_found":
                raise URLNotFoundException(f"URL不存在: {url}")
            elif fetch_result.error_type in ["http_error", "connection_error", "timeout"]:
                raise URLAccessFailedException(f"URL无法访问: {fetch_result.error_message}")
            else:
                # 其他错误类型，继续返回None让上层处理
                pass
        
        logger.info(f"❌ 通用DOI提取未找到结果")
        return None
        
    except Exception as e:
        logger.warning(f"通用DOI提取失败: {e}")
        return None


async def semantic_scholar_lookup_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """使用Semantic Scholar查询URL对应的论文"""
    try:
        logger.info(f"尝试Semantic Scholar URL查询: {url}")
        
        # 导入Semantic Scholar客户端
        from ....services.semantic_scholar import SemanticScholarClient
        
        client = SemanticScholarClient()
        
        # Semantic Scholar支持通过URL查询，但需要特定格式
        # 这里我们可以尝试搜索URL中的关键词
        # 注意：这是一个实验性功能，可能需要根据实际API调整
        
        # 暂时返回None，表示此策略尚未完全实现
        logger.debug("Semantic Scholar URL查询策略尚未完全实现")
        return None
        
    except Exception as e:
        logger.warning(f"Semantic Scholar查询失败: {e}")
        return None


class GenericAdapter(URLAdapter):
    """通用适配器 - 处理未知期刊的备选方案"""

    @property
    def name(self) -> str:
        return "generic"

    @property
    def supported_domains(self) -> List[str]:
        return []  # 不限制域名，作为最后的备选方案

    def can_handle(self, url: str) -> bool:
        # 总是返回True，但优先级最低，只有在其他适配器都失败时才会使用
        return True

    def _register_strategies(self):
        """注册通用支持的策略"""
        self.strategies = [
            # 策略1: 通用DOI提取（优先级最高）
            DatabaseStrategy("generic_doi_extraction", generic_doi_extraction_func, priority=1),
            
            # 策略2: Semantic Scholar查询（实验性）
            DatabaseStrategy("generic_semantic_scholar", semantic_scholar_lookup_func, priority=2),
        ]

    def extract_basic_info(self, url: str) -> URLMappingResult:
        """
        提取基本信息作为最后的备选方案
        
        Args:
            url: 要处理的URL
            
        Returns:
            包含基本信息的结果
        """
        result = URLMappingResult()
        result.source_page_url = url
        result.venue = "Unknown"
        result.source_adapter = self.name
        result.strategy_used = "generic_basic_fallback"
        result.confidence = 0.3  # 低置信度
        
        # 尝试从URL中提取DOI
        doi = DOIExtractor.extract_from_url(url)
        if doi:
            result.doi = doi
            result.confidence = 0.6  # 提高置信度
        
        return result
