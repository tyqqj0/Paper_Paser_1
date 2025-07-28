"""
Science适配器

处理Science期刊的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_science_match(match: re.Match, result: URLMappingResult,
                              pattern_name: str, url: str, context: Dict[str, Any]):
    """处理Science期刊URL匹配结果"""
    if pattern_name == "science_content":
        # 从URL路径提取信息: content/347/6220/1260419
        volume = match.group(1)
        issue = match.group(2)
        article_id = match.group(3)

        result.source_page_url = url
        result.venue = "Science"

        # 尝试构建Science DOI: 10.1126/science.{article_id}
        # Science的DOI格式通常是 10.1126/science.{article_id}
        if article_id.isdigit():
            constructed_doi = f"10.1126/science.{article_id}"
            result.doi = constructed_doi
            result.confidence = 0.85  # 中高置信度，因为是构建的DOI
        else:
            result.confidence = 0.8   # 较低置信度，无法构建DOI
            
        # 存储额外信息
        result.metadata.update({
            "volume": volume,
            "issue": issue,
            "article_id": article_id,
        })

    elif pattern_name == "science_doi":
        # 直接从URL中提取DOI
        doi = match.group(1)
        result.doi = doi
        result.source_page_url = url
        result.venue = "Science"
        result.confidence = 0.95
    elif pattern_name == "science_article":
        # 处理新格式的Science URL
        article_id = match.group(1)
        result.source_page_url = url
        result.venue = "Science"
        result.confidence = 0.85
    
    logger.debug(f"Science匹配成功，模式: {pattern_name}, DOI: {result.doi}")


class ScienceAdapter(URLAdapter):
    """Science适配器 - 处理Science期刊"""

    @property
    def name(self) -> str:
        return "science"

    @property
    def supported_domains(self) -> List[str]:
        return ["science.sciencemag.org", "www.science.org"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册Science支持的策略"""
        # Science正则策略
        science_patterns = {
            "science_content": r"science\.sciencemag\.org/content/(\d+)/(\d+)/(\d+)",
            "science_doi": r"(?:science\.sciencemag\.org|www\.science\.org)/doi/(?:abs/|full/)?(10\.\d{4}/[^?\s]+)",
            "science_article": r"(?:science\.sciencemag\.org|www\.science\.org)/content/article/([^?\s]+)",
        }

        self.strategies = [
            RegexStrategy("science_regex", science_patterns, process_science_match, priority=1),
            # 未来可以添加更多策略：
            # ScrapingStrategy("science_scraping", science_scraping_func, priority=2),
            # APIStrategy("science_api", science_api_func, priority=3),
        ]

    def extract_article_info(self, url: str) -> Dict[str, str]:
        """
        从Science URL中提取文章信息
        
        Args:
            url: Science URL
            
        Returns:
            包含文章信息的字典
        """
        # 匹配content格式: science.sciencemag.org/content/347/6220/1260419
        content_pattern = r"science\.sciencemag\.org/content/(\d+)/(\d+)/(\d+)"
        match = re.search(content_pattern, url, re.IGNORECASE)
        
        if match:
            return {
                "volume": match.group(1),
                "issue": match.group(2),
                "article_id": match.group(3),
            }
        
        return {}

    def construct_doi_from_article_id(self, article_id: str) -> str:
        """
        根据文章ID构建Science DOI
        
        Args:
            article_id: Science文章ID
            
        Returns:
            构建的DOI，如果无法构建则返回None
        """
        if article_id.isdigit():
            return f"10.1126/science.{article_id}"
        return None

    def extract_doi_from_url(self, url: str) -> str:
        """
        从Science URL中直接提取DOI
        
        Args:
            url: Science URL
            
        Returns:
            提取到的DOI，如果没有找到则返回None
        """
        doi_pattern = r"(?:science\.sciencemag\.org|www\.science\.org)/doi/(?:abs/|full/)?(10\.\d{4}/[^?\s]+)"
        match = re.search(doi_pattern, url, re.IGNORECASE)
        
        if match:
            return match.group(1)
        return None

    def get_science_urls(self, article_id: str) -> Dict[str, str]:
        """
        根据文章ID生成Science相关URL
        
        Args:
            article_id: Science文章ID
            
        Returns:
            包含各种URL的字典
        """
        doi = self.construct_doi_from_article_id(article_id)
        urls = {}
        
        if doi:
            urls.update({
                "doi": f"https://doi.org/{doi}",
                "science_doi": f"https://science.sciencemag.org/doi/{doi}",
            })
        
        return urls

    def is_valid_science_article_id(self, article_id: str) -> bool:
        """
        验证Science文章ID是否有效
        
        Args:
            article_id: 文章ID
            
        Returns:
            是否为有效的Science文章ID
        """
        # Science的文章ID通常是数字
        return article_id.isdigit() and len(article_id) >= 6
