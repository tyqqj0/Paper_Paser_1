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
            except requests.RequestException as e:
                 return ProcessorResult(success=False, error=f"Failed to download page: {e}", source=self.name)

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
