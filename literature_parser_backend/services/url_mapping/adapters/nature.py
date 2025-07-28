"""
Nature适配器

处理Nature系列期刊的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_nature_match(match: re.Match, result: URLMappingResult,
                             pattern_name: str, url: str, context: Dict[str, Any]):
    """处理Nature文章ID匹配结果"""
    article_id = match.group(1)
    result.source_page_url = url
    result.venue = "Nature"

    # 如果是DOI格式的文章ID，直接使用
    if article_id.startswith("s") or "nature" in article_id:
        result.doi = f"10.1038/{article_id}"
        result.confidence = 0.9
        # 添加警告：这是从URL构建的DOI，可能需要验证
        result.metadata['constructed_doi'] = True
        result.metadata['doi_source'] = 'url_pattern'
        result.metadata['warning'] = f"DOI {result.doi} 是从URL模式构建的，建议验证其真实性"
    else:
        # 对于其他格式，尝试构建DOI
        result.doi = f"10.1038/{article_id}"
        result.confidence = 0.7  # 降低置信度
        result.metadata['constructed_doi'] = True
        result.metadata['doi_source'] = 'url_pattern'
        result.metadata['warning'] = f"DOI {result.doi} 是从URL模式构建的，建议验证其真实性"
    
    logger.debug(f"Nature匹配成功，文章ID: {article_id}, DOI: {result.doi}")


class NatureAdapter(URLAdapter):
    """Nature适配器 - 处理Nature系列期刊"""

    @property
    def name(self) -> str:
        return "nature"

    @property
    def supported_domains(self) -> List[str]:
        return ["nature.com", "www.nature.com"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册Nature支持的策略"""
        # Nature正则策略
        nature_patterns = {
            "articles": r"nature\.com/articles/([^/?]+)",
            "nature_journal": r"nature\.com/nature/journal/[^/]+/[^/]+/[^/]+/([^/?]+)",
        }

        self.strategies = [
            RegexStrategy("nature_regex", nature_patterns, process_nature_match, priority=1),
            # 未来可以添加更多策略：
            # ScrapingStrategy("nature_scraping", nature_scraping_func, priority=2),
            # APIStrategy("nature_api", nature_api_func, priority=3),
        ]

    def extract_article_id(self, url: str) -> str:
        """
        从Nature URL中提取文章ID
        
        Args:
            url: Nature URL
            
        Returns:
            文章ID，如果没有找到则返回None
        """
        patterns = [
            r"nature\.com/articles/([^/?]+)",
            r"nature\.com/nature/journal/[^/]+/[^/]+/[^/]+/([^/?]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def construct_doi(self, article_id: str) -> str:
        """
        根据文章ID构建Nature DOI
        
        Args:
            article_id: Nature文章ID
            
        Returns:
            构建的DOI
        """
        return f"10.1038/{article_id}"

    def is_nature_doi_format(self, article_id: str) -> bool:
        """
        判断文章ID是否符合Nature DOI格式
        
        Args:
            article_id: 文章ID
            
        Returns:
            是否符合Nature DOI格式
        """
        # Nature的文章ID通常以's'开头或包含'nature'
        return article_id.startswith("s") or "nature" in article_id.lower()

    def get_nature_urls(self, article_id: str) -> Dict[str, str]:
        """
        根据文章ID生成Nature相关URL
        
        Args:
            article_id: Nature文章ID
            
        Returns:
            包含各种URL的字典
        """
        return {
            "article": f"https://www.nature.com/articles/{article_id}",
            "pdf": f"https://www.nature.com/articles/{article_id}.pdf",
            "doi": f"https://doi.org/10.1038/{article_id}",
        }

    def extract_journal_info(self, url: str) -> Dict[str, str]:
        """
        从Nature URL中提取期刊信息
        
        Args:
            url: Nature URL
            
        Returns:
            包含期刊信息的字典
        """
        # 匹配期刊URL格式: nature.com/nature/journal/v123/n456/full/article_id.html
        journal_pattern = r"nature\.com/([^/]+)/journal/v(\d+)/n(\d+)/[^/]+/([^/?]+)"
        match = re.search(journal_pattern, url, re.IGNORECASE)
        
        if match:
            return {
                "journal": match.group(1),
                "volume": match.group(2),
                "issue": match.group(3),
                "article_id": match.group(4),
            }
        
        return {}
