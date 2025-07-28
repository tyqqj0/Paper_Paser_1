"""
Cell适配器

处理Cell期刊的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_cell_match(match: re.Match, result: URLMappingResult,
                           pattern_name: str, url: str, context: Dict[str, Any]):
    """处理Cell期刊URL匹配结果"""
    if pattern_name == "cell_fulltext":
        # 从URL中提取文章ID: S0092-8674(23)00001-0
        article_id = match.group(1)
        result.source_page_url = url
        result.venue = "Cell"
        
        # Cell的DOI通常是 10.1016/j.cell.{year}.{month}.{day}
        # 但从URL中的格式很难直接构建，需要其他策略
        result.confidence = 0.8
        result.identifiers["cell_article_id"] = article_id
    elif pattern_name == "cell_doi":
        # 直接从URL中提取DOI
        doi = match.group(1)
        result.doi = doi
        result.source_page_url = url
        result.venue = "Cell"
        result.confidence = 0.95
    
    logger.debug(f"Cell匹配成功，模式: {pattern_name}")


class CellAdapter(URLAdapter):
    """Cell适配器 - 处理Cell期刊"""

    @property
    def name(self) -> str:
        return "cell"

    @property
    def supported_domains(self) -> List[str]:
        return ["www.cell.com", "cell.com"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册Cell支持的策略"""
        # Cell正则策略
        cell_patterns = {
            "cell_fulltext": r"cell\.com/cell/fulltext/([^?\s]+)",
            "cell_doi": r"cell\.com/(?:cell/)?(?:abstract|fulltext)/doi/(10\.\d{4}/[^?\s]+)",
        }

        self.strategies = [
            RegexStrategy("cell_regex", cell_patterns, process_cell_match, priority=1),
        ]

    def extract_article_id(self, url: str) -> str:
        """从Cell URL中提取文章ID"""
        pattern = r"cell\.com/cell/fulltext/([^?\s]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None
