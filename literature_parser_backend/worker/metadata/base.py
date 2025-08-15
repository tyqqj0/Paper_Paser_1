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


@dataclass
class IdentifierData:
    """Standardized input data for processors."""
    # Primary identifiers
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    
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
