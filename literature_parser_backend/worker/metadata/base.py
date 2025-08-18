"""
Base classes and interfaces for metadata processors.

Defines the unified interface that all metadata processors must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

from ...models.literature import MetadataModel


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
    
    def is_complete_parsing(self, completeness_threshold: float = 0.7) -> bool:
        """
        判断解析是否足够完整，可以停止后续处理器的尝试。
        
        Args:
            completeness_threshold: 完整性阈值，默认0.7表示需要70%的关键字段
            
        Returns:
            bool: True表示解析足够完整，可以停止；False表示需要继续尝试其他处理器
        """
        if not self.is_valid:
            return False
            
        metadata = self.metadata
        
        # 定义字段权重（总和为1.0）
        field_weights = {
            'title': 0.25,      # 标题最重要
            'authors': 0.20,    # 作者信息重要
            'year': 0.15,       # 年份重要
            'abstract': 0.15,   # 摘要重要
            'journal': 0.15,    # 期刊/会议重要
            'doi': 0.10         # DOI有用但不是必须的
        }
        
        # 计算当前完整性得分
        completeness_score = 0.0
        
        # 检查标题
        if metadata.title and metadata.title.strip() and metadata.title != "Unknown Title":
            completeness_score += field_weights['title']
            
        # 检查作者
        if metadata.authors and len(metadata.authors) > 0:
            # 检查是否有有效的作者名
            valid_authors = [a for a in metadata.authors if a.name and a.name.strip()]
            if valid_authors:
                completeness_score += field_weights['authors']
                
        # 检查年份
        if metadata.year and str(metadata.year).isdigit():
            year_int = int(metadata.year)
            if 1900 <= year_int <= 2030:  # 合理的年份范围
                completeness_score += field_weights['year']
                
        # 检查摘要
        if metadata.abstract and len(metadata.abstract.strip()) > 50:  # 至少50字符的摘要
            completeness_score += field_weights['abstract']
            
        # 检查期刊/会议
        if metadata.journal and metadata.journal.strip():
            completeness_score += field_weights['journal']
            
        # 检查DOI
        if metadata.doi and metadata.doi.strip():
            completeness_score += field_weights['doi']
            
        # 额外的质量检查：如果置信度很高，降低完整性要求
        adjusted_threshold = completeness_threshold
        if self.confidence > 0.8:
            adjusted_threshold = max(0.5, completeness_threshold - 0.2)
            
        return completeness_score >= adjusted_threshold
    



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
