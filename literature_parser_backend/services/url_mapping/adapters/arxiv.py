"""
ArXiv适配器

处理ArXiv预印本服务器的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_arxiv_match(match: re.Match, result: URLMappingResult,
                            pattern_name: str, url: str, context: Dict[str, Any]):
    """处理ArXiv ID匹配结果"""
    arxiv_id = match.group(1)
    result.arxiv_id = arxiv_id

    # 生成标准URL
    result.source_page_url = f"https://arxiv.org/abs/{arxiv_id}"
    result.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # 从ArXiv ID推断年份
    if re.match(r"\d{4}\.\d{4,5}", arxiv_id):
        year_str = arxiv_id[:2]
        # ArXiv从1991年开始，07年后使用4位年份
        if int(year_str) >= 7:
            result.year = 2000 + int(year_str)
        else:
            result.year = 2000 + int(year_str)
    
    result.confidence = 0.95
    logger.debug(f"ArXiv匹配成功，ID: {arxiv_id}")


class ArXivAdapter(URLAdapter):
    """ArXiv适配器 - 处理ArXiv预印本服务器"""

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def supported_domains(self) -> List[str]:
        return ["arxiv.org"]

    def can_handle(self, url: str) -> bool:
        return "arxiv.org" in url.lower()

    def _register_strategies(self):
        """注册ArXiv支持的策略"""
        # ArXiv正则策略
        arxiv_patterns = {
            "new_format": r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?",
            "old_format": r"arxiv\.org/(?:abs|pdf|html)/([a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?",
        }

        self.strategies = [
            RegexStrategy("arxiv_regex", arxiv_patterns, process_arxiv_match, priority=1),
            # 未来可以添加更多策略：
            # APIStrategy("arxiv_api", arxiv_api_func, priority=2),
            # DatabaseStrategy("arxiv_semantic_scholar", semantic_scholar_func, priority=3),
        ]

    def extract_arxiv_id(self, url: str) -> str:
        """
        从ArXiv URL中提取ArXiv ID
        
        Args:
            url: ArXiv URL
            
        Returns:
            ArXiv ID，如果没有找到则返回None
        """
        patterns = [
            r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?",
            r"arxiv\.org/(?:abs|pdf|html)/([a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def get_arxiv_urls(self, arxiv_id: str) -> Dict[str, str]:
        """
        根据ArXiv ID生成相关URL
        
        Args:
            arxiv_id: ArXiv ID
            
        Returns:
            包含各种URL的字典
        """
        return {
            "abstract": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            "source": f"https://arxiv.org/e-print/{arxiv_id}",
        }

    def is_new_format(self, arxiv_id: str) -> bool:
        """
        判断ArXiv ID是否为新格式（YYMM.NNNN）
        
        Args:
            arxiv_id: ArXiv ID
            
        Returns:
            是否为新格式
        """
        return bool(re.match(r"\d{4}\.\d{4,5}", arxiv_id))

    def extract_year_from_id(self, arxiv_id: str) -> int:
        """
        从ArXiv ID中提取年份
        
        Args:
            arxiv_id: ArXiv ID
            
        Returns:
            年份，如果无法提取则返回None
        """
        if self.is_new_format(arxiv_id):
            year_str = arxiv_id[:2]
            # ArXiv从1991年开始，07年后使用4位年份
            if int(year_str) >= 7:
                return 2000 + int(year_str)
            else:
                return 2000 + int(year_str)
        
        # 旧格式无法直接从ID提取年份
        return None
