"""
NeurIPS适配器

处理NeurIPS会议论文的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_neurips_match(match: re.Match, result: URLMappingResult,
                              pattern_name: str, url: str, context: Dict[str, Any]):
    """处理NeurIPS URL匹配结果"""
    year = int(match.group(1))

    result.year = year
    result.venue = "NeurIPS"
    result.pdf_url = url if url.endswith(".pdf") else None
    result.source_page_url = url if url.endswith(".html") else None
    result.confidence = 0.8
    
    logger.debug(f"NeurIPS匹配成功，年份: {year}")


class NeurIPSAdapter(URLAdapter):
    """NeurIPS适配器 - 处理NeurIPS会议论文"""

    @property
    def name(self) -> str:
        return "neurips"

    @property
    def supported_domains(self) -> List[str]:
        return ["proceedings.neurips.cc", "papers.nips.cc"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册NeurIPS支持的策略"""
        # NeurIPS正则策略
        neurips_patterns = {
            "neurips_paper": r"(?:proceedings\.neurips\.cc|papers\.nips\.cc)/paper/(\d{4})/(?:file|hash)/([^/]+)-(?:Paper\.pdf|Abstract\.html)",
            "neurips_hash": r"(?:proceedings\.neurips\.cc|papers\.nips\.cc)/paper/(\d{4})/hash/([^/]+)-Abstract\.html",
        }

        self.strategies = [
            RegexStrategy("neurips_regex", neurips_patterns, process_neurips_match, priority=1),
        ]

    def extract_year(self, url: str) -> int:
        """从NeurIPS URL中提取年份"""
        pattern = r"(?:proceedings\.neurips\.cc|papers\.nips\.cc)/paper/(\d{4})/"
        match = re.search(pattern, url, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def extract_paper_info(self, url: str) -> Dict[str, str]:
        """从NeurIPS URL中提取论文信息"""
        pattern = r"(?:proceedings\.neurips\.cc|papers\.nips\.cc)/paper/(\d{4})/(?:file|hash)/([^/]+)-(?:Paper\.pdf|Abstract\.html)"
        match = re.search(pattern, url, re.IGNORECASE)
        
        if match:
            return {
                "year": match.group(1),
                "paper_id": match.group(2),
            }
        
        return {}
