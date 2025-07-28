"""
PLOS适配器

处理PLOS ONE等PLOS期刊的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_plos_match(match: re.Match, result: URLMappingResult,
                           pattern_name: str, url: str, context: Dict[str, Any]):
    """处理PLOS ONE URL匹配结果"""
    doi = match.group(1)
    result.doi = doi
    result.source_page_url = url
    result.venue = "PLOS ONE"
    result.confidence = 0.95
    
    logger.debug(f"PLOS匹配成功，DOI: {doi}")


class PLOSAdapter(URLAdapter):
    """PLOS适配器 - 处理PLOS ONE等PLOS期刊"""

    @property
    def name(self) -> str:
        return "plos"

    @property
    def supported_domains(self) -> List[str]:
        return ["journals.plos.org"]

    def can_handle(self, url: str) -> bool:
        return "journals.plos.org" in url.lower()

    def _register_strategies(self):
        """注册PLOS支持的策略"""
        # PLOS正则策略
        plos_patterns = {
            "plos_article": r"journals\.plos\.org/[^/]+/article\?id=(10\.\d{4}/[^&\s]+)",
        }

        self.strategies = [
            RegexStrategy("plos_regex", plos_patterns, process_plos_match, priority=1),
        ]

    def extract_doi(self, url: str) -> str:
        """从PLOS URL中提取DOI"""
        pattern = r"journals\.plos\.org/[^/]+/article\?id=(10\.\d{4}/[^&\s]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None
