"""
验证策略

用于验证提取的标识符是否真实存在。
"""

import logging
import requests
from typing import Dict, Optional, Any

from ..core.base import IdentifierStrategy
from ..core.result import URLMappingResult

logger = logging.getLogger(__name__)


class DOIValidationStrategy(IdentifierStrategy):
    """DOI验证策略 - 通过CrossRef验证DOI是否存在"""

    def __init__(self, name: str = "doi_validation", priority: int = 10, timeout: int = 5):
        """
        初始化DOI验证策略
        
        Args:
            name: 策略名称
            priority: 优先级（通常设为最低，作为最后验证步骤）
            timeout: 请求超时时间（秒）
        """
        self._name = name
        self._priority = priority
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """
        验证已提取的DOI是否存在
        
        注意：这个策略不提取新的标识符，而是验证现有结果中的DOI
        """
        # 从上下文中获取已有的结果
        existing_result = context.get('current_result')
        if not existing_result or not existing_result.doi:
            logger.debug("没有DOI需要验证")
            return None

        doi = existing_result.doi
        logger.debug(f"开始验证DOI: {doi}")

        # 验证DOI是否存在
        is_valid = await self._validate_doi(doi)
        
        if is_valid:
            logger.info(f"✅ DOI验证通过: {doi}")
            # 提高置信度
            existing_result.confidence = min(existing_result.confidence + 0.1, 1.0)
            existing_result.metadata['doi_validated'] = True
            return existing_result
        else:
            logger.warning(f"❌ DOI验证失败: {doi}")
            # 降低置信度或标记为无效
            existing_result.confidence = max(existing_result.confidence - 0.3, 0.1)
            existing_result.metadata['doi_validated'] = False
            existing_result.metadata['validation_warning'] = f"DOI {doi} 可能不存在"
            
            # 根据配置决定是否返回结果
            strict_mode = context.get('strict_validation', False)
            if strict_mode:
                logger.info("严格模式：DOI验证失败，不返回结果")
                return None
            else:
                logger.info("宽松模式：DOI验证失败，但仍返回结果（降低置信度）")
                return existing_result

    async def _validate_doi(self, doi: str) -> bool:
        """
        通过CrossRef API验证DOI是否存在
        
        Args:
            doi: 要验证的DOI
            
        Returns:
            DOI是否存在
        """
        try:
            url = f"https://api.crossref.org/works/{doi}"
            
            # 使用异步请求（如果可用）或同步请求
            try:
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(url) as response:
                        return response.status == 200
            except ImportError:
                # 回退到同步请求
                response = requests.get(url, timeout=self.timeout)
                return response.status_code == 200
                
        except Exception as e:
            logger.warning(f"DOI验证请求失败: {e}")
            # 网络错误时，假设DOI有效（避免因网络问题误判）
            return True

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断是否需要验证
        
        只有当存在DOI且启用验证时才处理
        """
        existing_result = context.get('current_result')
        validation_enabled = context.get('enable_doi_validation', False)
        
        return (validation_enabled and 
                existing_result and 
                existing_result.doi and 
                not existing_result.metadata.get('doi_validated', False))


class ArXivValidationStrategy(IdentifierStrategy):
    """ArXiv ID验证策略 - 通过ArXiv API验证ID是否存在"""

    def __init__(self, name: str = "arxiv_validation", priority: int = 10, timeout: int = 5):
        self._name = name
        self._priority = priority
        self.timeout = timeout

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """验证已提取的ArXiv ID是否存在"""
        existing_result = context.get('current_result')
        if not existing_result or not existing_result.arxiv_id:
            return None

        arxiv_id = existing_result.arxiv_id
        logger.debug(f"开始验证ArXiv ID: {arxiv_id}")

        is_valid = await self._validate_arxiv_id(arxiv_id)
        
        if is_valid:
            logger.info(f"✅ ArXiv ID验证通过: {arxiv_id}")
            existing_result.confidence = min(existing_result.confidence + 0.1, 1.0)
            existing_result.metadata['arxiv_validated'] = True
            return existing_result
        else:
            logger.warning(f"❌ ArXiv ID验证失败: {arxiv_id}")
            existing_result.confidence = max(existing_result.confidence - 0.3, 0.1)
            existing_result.metadata['arxiv_validated'] = False
            existing_result.metadata['validation_warning'] = f"ArXiv ID {arxiv_id} 可能不存在"
            
            strict_mode = context.get('strict_validation', False)
            return None if strict_mode else existing_result

    async def _validate_arxiv_id(self, arxiv_id: str) -> bool:
        """通过ArXiv API验证ID是否存在"""
        try:
            url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
            
            try:
                import aiohttp
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            # 检查是否包含错误信息
                            return "No papers found" not in content
                        return False
            except ImportError:
                response = requests.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return "No papers found" not in response.text
                return False
                
        except Exception as e:
            logger.warning(f"ArXiv ID验证请求失败: {e}")
            return True  # 网络错误时假设有效

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """判断是否需要验证ArXiv ID"""
        existing_result = context.get('current_result')
        validation_enabled = context.get('enable_arxiv_validation', False)
        
        return (validation_enabled and 
                existing_result and 
                existing_result.arxiv_id and 
                not existing_result.metadata.get('arxiv_validated', False))
