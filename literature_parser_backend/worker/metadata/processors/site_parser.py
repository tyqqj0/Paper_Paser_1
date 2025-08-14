#!/usr/bin/env python3
"""
网站特定解析处理器 - Paper Parser 0.2

整合现有的URL适配器系统，为特定网站（NeurIPS、ACM、ArXiv等）
提供直接的元数据解析能力。当API失败时作为fallback。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ....models.literature import AuthorModel, MetadataModel
from ....services.url_mapping.core.service import URLMappingService
from ....services.url_mapping.core.result import URLMappingResult
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class SiteParserProcessor(MetadataProcessor):
    """
    网站特定解析处理器。
    
    利用现有的URL适配器系统直接从网站页面解析元数据。
    优先级：20（中等偏低，主要作为API失败后的fallback）
    """
    
    def __init__(self, settings=None):
        """初始化网站解析处理器"""
        super().__init__(settings)
        self.url_mapping_service = URLMappingService()
    
    @property
    def name(self) -> str:
        """处理器名称"""
        return "Site Parser"
    
    @property
    def processor_type(self) -> ProcessorType:
        """处理器类型"""
        return ProcessorType.SITE_PARSER
    
    @property
    def priority(self) -> int:
        """处理器优先级（中等偏低，主要作为fallback）"""
        return 20
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        检查是否可以处理给定的标识符。
        
        只有在有URL且不是PDF URL的情况下才能处理。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            True if 有可处理的URL
        """
        if not identifiers.url:
            return False
        
        # 检查是否是支持的网站URL
        supported_sites = [
            'proceedings.neurips.cc', 'papers.nips.cc',  # NeurIPS
            'dl.acm.org',  # ACM
            'arxiv.org',   # ArXiv
            'openaccess.thecvf.com',  # CVF
            'ieeexplore.ieee.org',  # IEEE
            'www.nature.com', 'nature.com',  # Nature
            'journals.plos.org',  # PLOS
            'science.sciencemag.org',  # Science
            'link.springer.com',  # Springer
            'www.cell.com'  # Cell
        ]
        
        url_lower = identifiers.url.lower()
        is_supported = any(site in url_lower for site in supported_sites)
        
        # 排除PDF URL（PDF解析由GROBID处理器负责）
        is_pdf = url_lower.endswith('.pdf')
        
        return is_supported and not is_pdf
    
    async def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        处理标识符并返回元数据。
        
        使用URL适配器系统解析网站页面，提取标题、作者、摘要等信息。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            ProcessorResult with 成功状态和元数据
        """
        try:
            if not identifiers.url:
                return ProcessorResult(
                    success=False,
                    error="Site Parser: No URL provided",
                    source=self.name
                )
            
            logger.info(f"🔍 网站解析: {identifiers.url}")
            
            # 使用URL适配器系统解析URL
            url_mapping_result = await self.url_mapping_service.map_url(
                identifiers.url,
                enable_validation=False,  # 跳过URL验证以提高速度
                skip_url_validation=True
            )
            
            if not url_mapping_result.has_useful_info():
                return ProcessorResult(
                    success=False,
                    error="Site Parser: No useful information extracted from URL",
                    source=self.name
                )
            
            # 转换URLMappingResult为MetadataModel
            metadata = self._convert_url_mapping_to_metadata(url_mapping_result)
            
            # 计算置信度（基于提取到的信息质量）
            confidence = self._calculate_confidence(url_mapping_result)
            
            logger.info(f"✅ 网站解析成功: title='{metadata.title}', venue='{metadata.journal}', confidence={confidence:.2f}")
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=self._url_mapping_result_to_dict(url_mapping_result),
                confidence=confidence,
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"网站解析处理器异常: {e}")
            return ProcessorResult(
                success=False,
                error=f"网站解析处理器异常: {str(e)}",
                source=self.name
            )
    
    def _convert_url_mapping_to_metadata(self, url_result: URLMappingResult) -> MetadataModel:
        """
        将URLMappingResult转换为标准的MetadataModel。
        
        Args:
            url_result: URL映射结果
            
        Returns:
            标准化的MetadataModel
        """
        # 提取标题
        title = url_result.title or "Unknown Title"
        
        # 提取作者（如果有的话）
        authors = []
        if hasattr(url_result, 'authors') and url_result.authors:
            for author_name in url_result.authors:
                if isinstance(author_name, str) and author_name.strip():
                    authors.append(AuthorModel(name=author_name.strip()))
        
        # 提取发表年份
        year = url_result.year
        
        # 提取期刊/会议信息
        journal = url_result.venue
        
        # 提取摘要（如果有的话）
        abstract = None
        if hasattr(url_result, 'abstract'):
            abstract = url_result.abstract
        elif url_result.metadata.get('abstract'):
            abstract = url_result.metadata['abstract']
        
        # 提取关键词（从metadata中）
        keywords = []
        if url_result.metadata.get('keywords'):
            keywords = url_result.metadata['keywords']
        elif url_result.metadata.get('categories'):
            keywords = url_result.metadata['categories']
        
        return MetadataModel(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=abstract,
            keywords=keywords,
            source_priority=[self.name]
        )
    
    def _calculate_confidence(self, url_result: URLMappingResult) -> float:
        """
        基于提取信息的质量计算置信度。
        
        Args:
            url_result: URL映射结果
            
        Returns:
            置信度分数 (0.0 - 1.0)
        """
        confidence = 0.3  # 基础分数
        
        # 有标题 +0.3
        if url_result.title and len(url_result.title.strip()) > 10:
            confidence += 0.3
        
        # 有DOI +0.2
        if url_result.doi:
            confidence += 0.2
        
        # 有ArXiv ID +0.15
        if url_result.arxiv_id:
            confidence += 0.15
        
        # 有年份 +0.1
        if url_result.year:
            confidence += 0.1
        
        # 有venue +0.1
        if url_result.venue:
            confidence += 0.1
        
        # 有摘要 +0.1
        if (hasattr(url_result, 'abstract') and url_result.abstract) or \
           url_result.metadata.get('abstract'):
            confidence += 0.1
        
        # 使用原始适配器的置信度作为参考
        if hasattr(url_result, 'confidence') and url_result.confidence:
            # 取两者的加权平均
            confidence = (confidence * 0.7) + (url_result.confidence * 0.3)
        
        return min(confidence, 1.0)
    
    def _url_mapping_result_to_dict(self, url_result: URLMappingResult) -> Dict[str, Any]:
        """
        将URLMappingResult转换为字典格式的raw_data。
        
        Args:
            url_result: URL映射结果
            
        Returns:
            字典格式的原始数据
        """
        return {
            'doi': url_result.doi,
            'arxiv_id': url_result.arxiv_id,
            'pmid': url_result.pmid,
            'title': url_result.title,
            'venue': url_result.venue,
            'year': url_result.year,
            'source_page_url': url_result.source_page_url,
            'pdf_url': url_result.pdf_url,
            'source_adapter': url_result.source_adapter,
            'strategy_used': url_result.strategy_used,
            'confidence': url_result.confidence,
            'identifiers': url_result.identifiers,
            'metadata': url_result.metadata,
            'has_identifiers': url_result.has_identifiers(),
            'has_useful_info': url_result.has_useful_info()
        }


# 自动注册处理器
from ..registry import register_processor
register_processor(SiteParserProcessor)


