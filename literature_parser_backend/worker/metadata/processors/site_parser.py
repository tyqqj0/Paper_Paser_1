"""
网站特定解析处理器 - V2

使用 requests 和 BeautifulSoup 直接从网页HTML中提取元数据，
不再依赖上层的 URLMappingService，避免逻辑循环。
"""

import logging
import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional, Tuple
import re

from ....models.literature import AuthorModel, MetadataModel
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)

# 为不同网站定义CSS选择器规则
SITE_RULES = {
    'proceedings.neurips.cc': {
        'title': 'h4.title',
        'authors': 'p.authors',
        'abstract': 'div.abstract > p',
        'year': '.shared-header-information h5, .shared-header-information p',
        'venue': '.shared-header-information h5, .shared-header-information p',
    },
    'papers.nips.cc': {
        'title': 'h2.title',
        'authors': 'div.main-container > p.author',
        'abstract': 'div.abstract > p',
        'year': 'div.main-container > h4',
        'venue': 'div.main-container > h4',
    },
    'dl.acm.org': {
        'title': 'h1.citation__title',
        'authors': 'ul.rlist--inline a[href^="/author/"]',
        'abstract': 'div.abstractSection > p',
        'year': 'span.epub-section__date',
        'venue': 'span.epub-section__title',
    },
    'ieeexplore.ieee.org': {
        'title': 'h1.document-title',
        'authors': 'div.authors-container span[class*="author-name"] a',
        'abstract': 'div.abstract-text > div',
        'year': 'div.u-pb-1 > span',
        'venue': 'div.u-pb-1 > a',
    },
    'openaccess.thecvf.com': {
        'title': 'div#papertitle',
        'authors': 'div#authors a',
        'abstract': 'div#abstract',
        'year': 'div.title',  # 年份通常在标题中
        'venue': 'div.title', # 会议信息在标题中
    },
    'cv-foundation.org': {
        'title': 'div#papertitle, title',
        'authors': 'div#authors a, i',
        'abstract': 'div#abstract, p',
        'year': 'div.title, body',
        'venue': 'div.title, body',
    },
    'proceedings.mlr.press': {
        'title': 'h1.title, .paper-title, title',
        'authors': '.authors .author, .paper-authors a',
        'abstract': '.abstract p, #abstract',
        'year': '.pub-details, .paper-venue',
        'venue': '.pub-details, .paper-venue',
    },
    'mlr.press': {
        'title': 'h1.title, .paper-title, title',
        'authors': '.authors .author, .paper-authors a',
        'abstract': '.abstract p, #abstract',
        'year': '.pub-details, .paper-venue',
        'venue': '.pub-details, .paper-venue',
    },
    'bioinf.jku.at': {
        'title': 'h1, title, .paper-title',
        'authors': '.authors, .author, p',
        'abstract': '.abstract, p',
        'year': 'body, .date, .year',
        'venue': 'body, .venue, .journal',
    },
    'jku.at': {
        'title': 'h1, title, .paper-title',
        'authors': '.authors, .author, p',
        'abstract': '.abstract, p',
        'year': 'body, .date, .year',
        'venue': 'body, .venue, .journal',
    },
    'nature.com': {
        'title': 'h1.c-article-title, h1[data-test="article-title"], .c-article__title',
        'authors': '.c-article-author-list__item a, .c-author-list a',
        'abstract': '.c-article-section__content p, div.c-article__summary p',
        'year': '.c-article-info-details time, .c-bibliographic-information__value',
        'venue': '.c-journal-title, .c-bibliographic-information__value',
    }
}


class SiteParserProcessor(MetadataProcessor):
    """
    网站特定解析处理器 V2。
    使用 requests 和 BeautifulSoup 直接从HTML中解析元数据。
    """
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
        })

    @property
    def name(self) -> str:
        return "Site Parser V2"
    
    @property
    def processor_type(self) -> ProcessorType:
        return ProcessorType.SITE_PARSER
    
    @property
    def priority(self) -> int:
        return 4
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        if not identifiers.url:
            return False
        
        url_lower = identifiers.url.lower()
        is_supported = any(site in url_lower for site in SITE_RULES.keys())
        is_pdf = url_lower.endswith('.pdf')
        
        return is_supported and not is_pdf
    
    def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        同步处理标识符并返回元数据。
        """
        try:
            if not identifiers.url:
                return ProcessorResult(success=False, error="No URL provided", source=self.name)
            
            logger.info(f"🔍 [SiteParserV2] Parsing URL: {identifiers.url}")
            
            domain = next((site for site in SITE_RULES.keys() if site in identifiers.url.lower()), None)
            if not domain:
                return ProcessorResult(success=False, error="No matching rule found for this site", source=self.name)
            
            rules = SITE_RULES[domain]
            
            try:
                response = self.session.get(identifiers.url, timeout=15)
                response.raise_for_status()
                html_content = response.text
            except requests.HTTPError as e:
                # 检查HTTP状态码
                if response.status_code == 404:
                    return ProcessorResult(success=False, error="url_not_found", source=self.name)
                elif response.status_code >= 500:
                    return ProcessorResult(success=False, error="url_access_failed", source=self.name)
                else:
                    return ProcessorResult(success=False, error=f"HTTP error {response.status_code}: {e}", source=self.name)
            except requests.RequestException as e:
                return ProcessorResult(success=False, error="url_access_failed", source=self.name)

            soup = BeautifulSoup(html_content, 'html.parser')

            # Defensive extraction for each field
            title, authors, abstract, year, venue = "Unknown Title", [], None, None, None
            try:
                title = soup.select_one(rules['title']).get_text(strip=True) if soup.select_one(rules['title']) else "Unknown Title"
            except Exception as e:
                logger.warning(f"[SiteParserV2] Failed to parse title for {identifiers.url}: {e}")
            
            try:
                authors_elements = soup.select(rules['authors'])
                authors = [AuthorModel(name=el.get_text(strip=True)) for el in authors_elements]
            except Exception as e:
                logger.warning(f"[SiteParserV2] Failed to parse authors for {identifiers.url}: {e}")

            try:
                abstract = soup.select_one(rules['abstract']).get_text(strip=True) if soup.select_one(rules['abstract']) else None
            except Exception as e:
                logger.warning(f"[SiteParserV2] Failed to parse abstract for {identifiers.url}: {e}")
            
            try:
                year_text = soup.select_one(rules['year']).get_text(strip=True) if soup.select_one(rules['year']) else ''
                year_match = re.search(r'\b(19|20)\d{2}\b', year_text)
                year = year_match.group(0) if year_match else None
            except Exception as e:
                logger.warning(f"[SiteParserV2] Failed to parse year for {identifiers.url}: {e}")

            try:
                venue = soup.select_one(rules['venue']).get_text(strip=True) if soup.select_one(rules['venue']) else None
            except Exception as e:
                logger.warning(f"[SiteParserV2] Failed to parse venue for {identifiers.url}: {e}")

            # 🆕 如果规则提取失败或结果不完整，尝试meta标签回退
            if (title == "Unknown Title" or not authors or not abstract or not year or not venue):
                logger.info(f"[SiteParserV2] 规则提取不完整，尝试meta标签回退: {identifiers.url}")
                meta_title, meta_authors, meta_abstract, meta_year, meta_venue = self._extract_from_meta_tags(soup, identifiers.url)
                
                # 用更好的数据替换空缺字段
                if title == "Unknown Title" and meta_title != "Unknown Title":
                    title = meta_title
                if not authors and meta_authors:
                    authors = meta_authors
                if not abstract and meta_abstract:
                    abstract = meta_abstract
                if not year and meta_year:
                    year = meta_year
                if not venue and meta_venue:
                    venue = meta_venue
                    
                logger.info(f"[SiteParserV2] Meta标签增强完成，作者: {len(authors)}个")

            metadata = MetadataModel(
                title=title,
                authors=authors,
                year=year,
                journal=venue,
                abstract=abstract,
                source_priority=[self.name]
            )

            confidence = self._calculate_confidence(metadata)
            
            if not metadata.title or metadata.title == "Unknown Title":
                return ProcessorResult(success=False, error="Failed to extract a valid title", source=self.name)

            logger.info(f"✅ [SiteParserV2] Successfully parsed: title='{metadata.title}', confidence={confidence:.2f}")

            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data={'source_url': identifiers.url},
                confidence=confidence,
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"[SiteParserV2] Exception during processing {identifiers.url}: {e}", exc_info=True)
            return ProcessorResult(success=False, error=f"An unexpected error occurred: {e}", source=self.name)
            
    def _extract_from_meta_tags(self, soup, url: str):
        """从meta标签中提取数据（学术网站的标准方式）"""
        title = "Unknown Title"
        authors = []
        abstract = None
        year = None
        venue = None
        
        try:
            # 提取标题
            title_meta = soup.find('meta', {'name': 'citation_title'}) or soup.find('meta', {'property': 'og:title'})
            if title_meta:
                title = title_meta.get('content', '').strip()
                logger.debug(f"[SiteParserV2] Meta标签提取标题: {title}")
            
            # 提取作者
            author_metas = soup.find_all('meta', {'name': 'citation_author'})
            for author_meta in author_metas:
                author_name = author_meta.get('content', '').strip()
                if author_name:
                    authors.append(AuthorModel(name=author_name))
            
            if authors:
                logger.debug(f"[SiteParserV2] Meta标签提取作者: {len(authors)}个")
            
            # 提取摘要
            abstract_meta = soup.find('meta', {'name': 'citation_abstract'}) or soup.find('meta', {'property': 'og:description'})
            if abstract_meta:
                abstract = abstract_meta.get('content', '').strip()
                logger.debug(f"[SiteParserV2] Meta标签提取摘要: {len(abstract)}字符")
            
            # 提取年份
            year_meta = soup.find('meta', {'name': 'citation_publication_date'}) or soup.find('meta', {'name': 'citation_date'})
            if year_meta:
                date_text = year_meta.get('content', '')
                year_match = re.search(r'\b(19|20)\d{2}\b', date_text)
                if year_match:
                    year = year_match.group(0)
                    logger.debug(f"[SiteParserV2] Meta标签提取年份: {year}")
            
            # 提取期刊/会议
            venue_meta = soup.find('meta', {'name': 'citation_journal_title'}) or soup.find('meta', {'name': 'citation_conference_title'})
            if venue_meta:
                venue = venue_meta.get('content', '').strip()
                logger.debug(f"[SiteParserV2] Meta标签提取期刊: {venue}")
            
        except Exception as e:
            logger.warning(f"[SiteParserV2] Meta标签提取异常: {url}, 错误: {e}")
        
        return title, authors, abstract, year, venue

    def _calculate_confidence(self, metadata: MetadataModel) -> float:
        confidence = 0.0
        if metadata.title and metadata.title != "Unknown Title": confidence += 0.4
        if metadata.authors: confidence += 0.3
        if metadata.year: confidence += 0.1
        if metadata.journal: confidence += 0.1
        if metadata.abstract: confidence += 0.1
        return min(confidence, 1.0)


# 自动注册处理器
from ..registry import register_processor
register_processor(SiteParserProcessor)
