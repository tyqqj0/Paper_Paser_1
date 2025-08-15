"""
ACM适配器

处理ACM Digital Library的URL映射。
"""

import re
import logging
from typing import List, Dict, Any, Optional

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_acm_match(match: re.Match, result: URLMappingResult,
                          pattern_name: str, url: str, context: Dict[str, Any]):
    """处理ACM Digital Library URL匹配结果"""
    doi = match.group(1)
    result.doi = doi
    result.source_page_url = url
    result.venue = "ACM"
    result.confidence = 0.95
    
    logger.debug(f"ACM匹配成功，DOI: {doi}")


class ACMAdapter(URLAdapter):
    """ACM适配器 - 处理ACM Digital Library"""

    @property
    def name(self) -> str:
        return "acm"

    @property
    def supported_domains(self) -> List[str]:
        return ["dl.acm.org", "portal.acm.org"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册ACM支持的策略"""
        # ACM正则策略
        acm_patterns = {
            "acm_doi": r"dl\.acm\.org/doi/(?:abs/|full/)?(10\.\d{4}/[^?\s]+)",
            "acm_citation": r"dl\.acm\.org/citation\.cfm\?id=(\d+)",
        }

        self.strategies = [
            RegexStrategy("acm_regex", acm_patterns, process_acm_match, priority=1),
        ]

    def extract_doi(self, url: str) -> str:
        """从ACM URL中提取DOI"""
        pattern = r"dl\.acm\.org/doi/(?:abs/|full/)?(10\.\d{4}/[^?\s]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None

    async def extract_identifier_from_url(self, url: str) -> Optional[URLMappingResult]:
        """
        直接从URL中提取DOI作为主要标识符，无需进行HTTP请求。
        
        Args:
            url: 输入URL字符串
            
        Returns:
            URLMappingResult 如果成功提取到DOI，否则None。
        """
        doi = self.extract_doi(url)
        if doi:
            logger.info(f"[ACMAdapter] 直接从URL中提取到DOI: {doi}")
            return URLMappingResult(
                doi=doi,
                source_page_url=url,
                venue="ACM",
                confidence=0.98, # 直接从URL提取DOI，置信度非常高
                source_adapter="acm_url_extraction"
            )
        return None
