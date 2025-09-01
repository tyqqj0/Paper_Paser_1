"""
Base classes and interfaces for metadata processors.

Defines the unified interface that all metadata processors must implement.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from ...models.literature import MetadataModel

logger = logging.getLogger(__name__)


class ProcessorType(Enum):
    """Type of metadata processor."""
    API = "api"                    # External API (CrossRef, Semantic Scholar)
    SITE_PARSER = "site_parser"    # Website content parsing
    PDF_PARSER = "pdf_parser"      # PDF content extraction
    FALLBACK = "fallback"          # Last resort fallback


# 移除了PaperType枚举，改用简单的必需字段检查


@dataclass
class IdentifierData:
    """Standardized input data for processors."""
    # Primary identifiers
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    
    # URL-based identifiers
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    
    # Extracted metadata (from URL mapping)
    title: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: Optional[List[str]] = None  # 🆕 添加作者字段支持
    
    # Additional context
    source_data: Optional[Dict[str, Any]] = None
    pdf_content: Optional[bytes] = None
    file_path: Optional[str] = None  # Local file path


@dataclass
class ProcessorResult:
    """Standardized output from processors."""
    success: bool
    metadata: Optional[MetadataModel] = None
    raw_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0
    source: str = ""
    new_identifiers: Optional[Dict[str, str]] = None  # 承载新发现的标识符
    
    @property
    def is_valid(self) -> bool:
        """Check if result contains valid metadata."""
        return self.success and self.metadata is not None
    
    def extract_new_identifiers(self) -> Dict[str, str]:
        """
        从metadata中提取新发现的标识符，特别是DOI。
        
        Returns:
            Dict[str, str]: 新发现的标识符字典
        """
        if not self.metadata:
            return {}
        
        identifiers = {}
        
        # 提取DOI
        if hasattr(self.metadata, 'doi') and self.metadata.doi:
            doi_value = self.metadata.doi.strip()
            if doi_value and doi_value.lower() != 'none':
                identifiers['doi'] = doi_value
        
        # 提取ArXiv ID（如果有external_ids）
        if hasattr(self.metadata, 'external_ids') and self.metadata.external_ids:
            if isinstance(self.metadata.external_ids, dict):
                arxiv_id = self.metadata.external_ids.get('ArXiv') or self.metadata.external_ids.get('arxiv')
                if arxiv_id:
                    identifiers['arxiv_id'] = arxiv_id.strip()
        
        # 合并已有的new_identifiers
        if self.new_identifiers:
            identifiers.update(self.new_identifiers)
        
        return identifiers
    
    def get_parsing_score(self) -> float:
        """
        计算解析的分数（0.0-1.0+）
        
        评分算法：
        - 必要字段（title, authors, year）：缺一个就乘以0.3惩罚系数
        - 可选字段（abstract, journal, doi）：有就奖励，没有就轻微惩罚
        - 返回最终分数，满分可能超过1.0
        
        Returns:
            float: 解析分数，0.0表示零分（无效），>0.0表示有价值，>=1.0表示满分
        """
        if not self.is_valid:
            logger.debug("🔍 [评分] 结果无效，返回0分")
            return 0.0
            
        metadata = self.metadata
        
        # 基础分数，从1.0开始
        score = 1.0
        
        # === 必要字段检查（缺一个就严重惩罚） ===
        required_fields_missing = 0
        
        # 检查标题
        if not (metadata.title and metadata.title.strip() and metadata.title != "Unknown Title"):
            required_fields_missing += 1
            title_info = metadata.title[:50] if metadata.title else "None"
            logger.debug(f"🔍 [评分] 标题无效: '{title_info}'")
        else:
            logger.debug(f"🔍 [评分] 标题有效: '{metadata.title[:50]}'")
            
        # 检查作者
        valid_authors = []
        if metadata.authors and len(metadata.authors) > 0:
            valid_authors = [a for a in metadata.authors if a.name and a.name.strip()]
        if not valid_authors:
            required_fields_missing += 1
            author_count = len(metadata.authors) if metadata.authors else 0
            logger.debug(f"🔍 [评分] 作者无效: 总数{author_count}，有效0个")
        else:
            author_names = [a.name for a in valid_authors[:3]]
            logger.debug(f"🔍 [评分] 作者有效: {len(valid_authors)}个 {author_names}")
                
        # 检查年份
        valid_year = False
        if metadata.year and str(metadata.year).isdigit():
            year_int = int(metadata.year)
            if 1900 <= year_int <= 2030:  # 合理的年份范围
                valid_year = True
        if not valid_year:
            required_fields_missing += 1
            logger.debug(f"🔍 [评分] 年份无效: '{metadata.year}'")
        else:
            logger.debug(f"🔍 [评分] 年份有效: {metadata.year}")
        
        # 必要字段惩罚：每缺一个字段，分数乘以0.3
        if required_fields_missing > 0:
            old_score = score
            score *= (0 ** required_fields_missing)
            logger.debug(f"🔍 [评分] 必要字段缺失{required_fields_missing}个，分数从{old_score:.3f}降至{score:.3f}")
        else:
            logger.debug("🔍 [评分] 必要字段完整，保持基础分数1.0")
        
        # === 可选字段检查（有奖励，没有轻微惩罚） ===
        optional_bonus = 1.0
        
        # 检查摘要（有价值的可选字段）
        if metadata.abstract and len(metadata.abstract.strip()) > 50:
            optional_bonus *= 1  # 20% 奖励
            logger.debug(f"🔍 [评分] 有效摘要({len(metadata.abstract.strip())}字符)")
        else:
            optional_bonus *= 0.5  # 5% 惩罚
            abstract_len = len(metadata.abstract.strip()) if metadata.abstract else 0
            logger.debug(f"🔍 [评分] 摘要不足({abstract_len}字符)，惩罚5%")
            
        # 检查期刊/会议（有价值的可选字段）
        if metadata.journal and metadata.journal.strip():
            optional_bonus *= 1  # 15% 奖励
            logger.debug(f"🔍 [评分] 有期刊信息({metadata.journal[:30]})")
        else:
            optional_bonus *= 0.5  # 5% 惩罚
            logger.debug("🔍 [评分] 无期刊信息，惩罚5%")
            
        # 检查标识符（DOI、ArXiv ID等 - 对后续处理器很重要）
        has_identifiers = False
        identifier_bonus = 1.0
        
        # 检查DOI（从new_identifiers中获取）
        doi_found = False
        if self.new_identifiers and self.new_identifiers.get('doi'):
            doi_found = True
            has_identifiers = True
            identifier_bonus *= 4.0  # 🆕 有DOI是巨大优势，4倍奖励
            logger.debug(f"🔍 [评分] 有DOI({self.new_identifiers['doi']}) - 4倍奖励！")
        else:
            logger.debug("🔍 [评分] 无DOI")
        
        # 检查ArXiv ID（从new_identifiers中获取）
        arxiv_id_found = False
        if self.new_identifiers and self.new_identifiers.get('arxiv_id'):
            arxiv_id_found = True
            has_identifiers = True
            identifier_bonus *= 4.0  # 🆕 有ArXiv ID也是巨大优势，4倍奖励
            logger.debug(f"🔍 [评分] 有ArXiv ID({self.new_identifiers['arxiv_id']}) - 4倍奖励！")
        else:
            logger.debug("🔍 [评分] 无ArXiv ID")
        
        # 如果没有任何标识符，给予惩罚（因为其他处理器无法工作）
        if not has_identifiers:
            identifier_bonus *= 0.25   # 75% 惩罚
            logger.debug("🔍 [评分] 无任何标识符(DOI/ArXiv)，惩罚75% - 其他处理器难以工作")
        else:
            logger.debug(f"🔍 [评分] 有重要标识符 - DOI:{doi_found}, ArXiv:{arxiv_id_found}")
        
        # 最终分数
        final_score = score * optional_bonus * identifier_bonus
        logger.debug(f"🔍 [评分] 最终得分: {score:.3f} × {optional_bonus:.3f} × {identifier_bonus:.3f} = {final_score:.3f}")
        return final_score
    
    def is_complete_parsing(self, completeness_threshold: float = 0.7) -> bool:
        """
        判断解析是否足够完整，可以停止后续处理器的尝试。
        
        基于get_parsing_score()的结果：
        - 满分(>=1.0) → 立即停止
        - 达到阈值 → 可以停止，但可能继续寻找更好的
        
        Args:
            completeness_threshold: 完整性阈值，默认0.7
            
        Returns:
            bool: True表示解析足够完整，可以停止；False表示需要继续尝试其他处理器
        """
        score = self.get_parsing_score()
        
        # 满分情况：所有必要+可选字段都有
        if score >= 1.0:
            return True  # 满分直接通过
        
        # 高置信度时降低要求
        adjusted_threshold = completeness_threshold
        if self.confidence > 0.8:
            adjusted_threshold = max(0.5, completeness_threshold - 0.2)
            
        return score >= adjusted_threshold
    
    def is_zero_score(self) -> bool:
        """判断是否为零分（完全无效的结果）"""
        return self.get_parsing_score() <= 0.0
    



class MetadataProcessor(ABC):
    """
    Abstract base class for all metadata processors.
    
    All processors (API clients, site parsers, PDF parsers) must implement
    this interface to ensure consistent behavior and easy integration.
    """
    
    def __init__(self, settings=None):
        """Initialize processor with optional settings."""
        self.settings = settings
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this processor."""
        pass
    
    @property
    @abstractmethod
    def processor_type(self) -> ProcessorType:
        """Type of this processor."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Priority of this processor (lower = higher priority).
        
        Suggested ranges:
        - 1-10: Primary APIs (CrossRef, Semantic Scholar)
        - 11-20: Secondary APIs (arXiv Official)
        - 21-30: Site parsers (NeurIPS, ACM)
        - 31-40: PDF parsers (GROBID)
        - 91-99: Fallbacks
        """
        pass
    
    @abstractmethod
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        Check if this processor can handle the given identifiers.
        
        Args:
            identifiers: Standardized identifier data
            
        Returns:
            True if this processor can attempt to fetch metadata
        """
        pass
    
    @abstractmethod
    async def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        Process identifiers and return metadata.
        
        Args:
            identifiers: Standardized identifier data
            
        Returns:
            ProcessorResult with success status and metadata
        """
        pass
    
    def __str__(self) -> str:
        """String representation for debugging."""
        return f"{self.name} (priority: {self.priority})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return f"{self.__class__.__name__}(name='{self.name}', priority={self.priority})"
