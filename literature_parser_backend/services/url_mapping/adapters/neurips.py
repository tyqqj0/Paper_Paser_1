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
from bs4 import BeautifulSoup
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
    """从NeurIPS页面抓取元数据和DOI - 优先使用结构化元数据"""
    result = URLMappingResult()
    
    try:
        # 只处理Abstract页面
        if not url.endswith("-Abstract.html"):
            return result
            
        logger.debug(f"开始抓取NeurIPS页面: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    logger.warning(f"NeurIPS页面访问失败，状态码: {response.status}")
                    return result
                    
                html_content = await response.text()
        
        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 优先级1: 提取结构化meta标签 (Dublin Core, Citation等)
        title = None
        authors = []
        
        # 尝试citation_* meta标签 (最可靠)
        meta_title = soup.find('meta', attrs={'name': 'citation_title'})
        if meta_title and meta_title.get('content'):
            title = meta_title['content'].strip()
            logger.info(f"[NeurIPS Meta] 找到citation_title: {title}")
        
        meta_authors = soup.find_all('meta', attrs={'name': 'citation_author'})
        if meta_authors:
            authors = [meta.get('content', '').strip() for meta in meta_authors if meta.get('content')]
            logger.info(f"[NeurIPS Meta] 找到authors: {len(authors)}个")
        
        # 尝试Dublin Core标签
        if not title:
            dc_title = soup.find('meta', attrs={'name': 'DC.title'}) or soup.find('meta', attrs={'name': 'dc.title'})
            if dc_title and dc_title.get('content'):
                title = dc_title['content'].strip()
                logger.info(f"[NeurIPS Meta] 找到DC.title: {title}")
        
        # 优先级2: CSS选择器提取 (作为fallback)
        if not title:
            # NeurIPS的主标题通常在这些位置
            title_selectors = [
                'h4',  # 主标题
                '.paper-title',
                '.title',
                'h1', 'h2', 'h3'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    candidate_title = title_elem.get_text(strip=True)
                    # 验证标题质量（避免提取到导航元素）
                    if candidate_title and len(candidate_title) > 10 and 'neurips' not in candidate_title.lower():
                        title = candidate_title
                        logger.info(f"[NeurIPS CSS] 找到标题: {title} (选择器: {selector})")
                        break
        
        # 如果仍未找到标题，尝试页面title标签作为最后手段
        if not title:
            page_title = soup.find('title')
            if page_title:
                candidate_title = page_title.get_text(strip=True)
                # 清理页面标题（通常包含网站名）
                if ' | ' in candidate_title:
                    candidate_title = candidate_title.split(' | ')[0].strip()
                if candidate_title and len(candidate_title) > 10:
                    title = candidate_title
                    logger.info(f"[NeurIPS Title] 找到页面标题: {title}")
        
        result.title = title
        
        # 提取年份和venue
        year_match = re.search(r'/paper/(\d{4})/', url)
        if year_match:
            result.year = int(year_match.group(1))
            result.venue = "NeurIPS"
        
        # 如果找到authors，添加到结果
        if authors:
            result.authors = authors[:5]  # 限制作者数量，避免过多
        
        # 优先级1: 从meta标签提取DOI
        meta_doi = soup.find('meta', attrs={'name': 'citation_doi'})
        if meta_doi and meta_doi.get('content'):
            doi = meta_doi['content'].strip()
            if doi.startswith('10.'):
                result.doi = doi
                logger.info(f"[NeurIPS Meta] 找到DOI: {result.doi}")
        
        # 优先级2: 从页面链接中查找DOI (fallback)
        if not result.doi:
            doi_links = soup.find_all('a', href=lambda x: x and 'doi.org' in x)
            for link in doi_links:
                href = link.get('href', '')
                doi_match = re.search(r'doi\.org/([0-9.]+/[^\s"\'>?#]+)', href)
                if doi_match:
                    doi = doi_match.group(1).strip()
                    if doi.startswith('10.'):
                        result.doi = doi
                        logger.info(f"[NeurIPS Link] 找到DOI: {result.doi}")
                        break
        
        # 查找ArXiv链接 - 使用BeautifulSoup更精确
        arxiv_links = soup.find_all('a', href=lambda x: x and 'arxiv.org' in x)
        for link in arxiv_links:
            href = link.get('href', '')
            arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^/?"\'>]+)', href)
            if arxiv_match:
                arxiv_id = arxiv_match.group(1).replace('.pdf', '')
                if arxiv_id:
                    result.arxiv_id = arxiv_id
                    logger.info(f"[NeurIPS Link] 找到ArXiv ID: {result.arxiv_id}")
                    break
        
        # 设置其他信息
        result.source_page_url = url
        
        # 动态计算置信度
        confidence = 0.5  # 基础分
        if result.title: confidence += 0.3
        if result.doi: confidence += 0.15
        if result.arxiv_id: confidence += 0.1
        if authors: confidence += 0.1
        if result.year: confidence += 0.05
        
        result.confidence = min(confidence, 1.0)
        
        logger.info(f"NeurIPS页面解析完成: title={bool(result.title)}, doi={bool(result.doi)}, arxiv={bool(result.arxiv_id)}, authors={len(authors)}, confidence={result.confidence:.2f}")
        
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