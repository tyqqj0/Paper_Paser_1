"""
Springer适配器

处理Springer期刊的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_springer_match(match: re.Match, result: URLMappingResult,
                               pattern_name: str, url: str, context: Dict[str, Any]):
    """处理Springer URL匹配结果"""
    doi = match.group(1)
    result.doi = doi
    result.source_page_url = url
    result.venue = "Springer"
    result.confidence = 0.95
    
    logger.debug(f"Springer匹配成功，DOI: {doi}")


class SpringerAdapter(URLAdapter):
    """Springer适配器 - 处理Springer期刊"""

    @property
    def name(self) -> str:
        return "springer"

    @property
    def supported_domains(self) -> List[str]:
        return ["link.springer.com", "www.springer.com"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册Springer支持的策略"""
        # Springer正则策略
        springer_patterns = {
            "springer_article": r"link\.springer\.com/article/(10\.\d{4}/[^?\s]+)",
        }

        self.strategies = [
            RegexStrategy("springer_regex", springer_patterns, process_springer_match, priority=1),
        ]

    def extract_doi(self, url: str) -> str:
        """从Springer URL中提取DOI"""
        pattern = r"link\.springer\.com/article/(10\.\d{4}/[^?\s]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None
