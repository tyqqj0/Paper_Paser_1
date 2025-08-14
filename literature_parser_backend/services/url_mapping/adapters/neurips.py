"""
NeurIPS适配器

处理NeurIPS会议论文的URL映射。
"""

import re
import logging
import aiohttp
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy
from ..strategies.scraping_strategy import ScrapingStrategy

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


async def scrape_neurips_page(url: str, context: Dict[str, Any]) -> URLMappingResult:
    """从NeurIPS页面抓取元数据和DOI"""
    result = URLMappingResult()
    
    try:
        # 只处理Abstract页面
        if not url.endswith("-Abstract.html"):
            return result
            
        logger.debug(f"开始抓取NeurIPS页面: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"NeurIPS页面访问失败，状态码: {response.status}")
                    return result
                    
                html_content = await response.text()
        
        # 使用正则表达式提取标题
        title_patterns = [
            r'<h4[^>]*>([^<]*ImageNet[^<]*)</h4>',  # 包含ImageNet的h4标题
            r'<h4[^>]*>([^<]+)</h4>',              # 任何h4标题
            r'<title>([^<]+)</title>',             # title标签
        ]
        
        for pattern in title_patterns:
            title_match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # 清理标题中的HTML标签和特殊字符
                title = re.sub(r'<[^>]+>', '', title)
                title = re.sub(r'\s+', ' ', title).strip()
                if title and len(title) > 10:  # 确保是有意义的标题
                    result.title = title
                    logger.debug(f"提取到标题: {title}")
                    break
        
        # 提取年份和venue
        year_match = re.search(r'/paper/(\d{4})/', url)
        if year_match:
            result.year = int(year_match.group(1))
            result.venue = "NeurIPS"
        
        # 尝试查找DOI (从meta标签中)
        doi_patterns = [
            r'<meta[^>]*name=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']citation_doi["\']',
            r'doi\.org/([0-9.]+/[^\s"\'<>]+)',  # 页面中的DOI链接
        ]
        
        for pattern in doi_patterns:
            doi_match = re.search(pattern, html_content, re.IGNORECASE)
            if doi_match:
                doi = doi_match.group(1).strip()
                if doi.startswith('10.'):
                    result.doi = doi
                    logger.info(f"找到DOI: {result.doi}")
                    break
        
        # 查找ArXiv链接
        arxiv_pattern = r'href=["\']([^"\']*arxiv\.org/(?:abs|pdf)/([^/?"\'>]+))["\']'
        arxiv_matches = re.finditer(arxiv_pattern, html_content, re.IGNORECASE)
        
        for match in arxiv_matches:
            arxiv_id = match.group(2).replace('.pdf', '')
            if arxiv_id:
                result.arxiv_id = arxiv_id
                logger.info(f"找到ArXiv ID: {result.arxiv_id}")
                break
        
        # 设置其他信息
        result.source_page_url = url
        result.confidence = 0.9 if result.title else 0.7
        
        logger.info(f"NeurIPS页面解析完成: title={bool(result.title)}, doi={bool(result.doi)}, arxiv={bool(result.arxiv_id)}")
        
    except Exception as e:
        logger.error(f"NeurIPS页面解析失败: {e}")
        
    return result


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
            # 优先使用页面抓取策略获取完整元数据
            ScrapingStrategy("neurips_scraping", scrape_neurips_page, priority=1),
            # 备用正则策略
            RegexStrategy("neurips_regex", neurips_patterns, process_neurips_match, priority=2),
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
