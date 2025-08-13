"""
Base Literature Matcher

Defines the core interfaces and data models for literature matching.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MatchType(Enum):
    """Types of matching scenarios with different precision requirements."""
    DEDUPLICATION = "dedup"      # 查重场景：高精度，避免误判
    CITATION = "citation"        # 引用场景：高召回，捕获更多引用
    GENERAL = "general"          # 通用场景：平衡精度和召回


class MatchResult(BaseModel):
    """Result of a literature matching operation."""
    lid: str = Field(..., description="匹配到的文献LID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="匹配置信度")
    matched_fields: List[str] = Field(default_factory=list, description="匹配成功的字段")
    match_details: Dict[str, Any] = Field(default_factory=dict, description="详细匹配信息")
    source_data: Optional[Dict[str, Any]] = Field(None, description="原始匹配数据")


class MatchStrategy(ABC):
    """Abstract base class for matching strategies."""
    
    @abstractmethod
    async def calculate_similarity(
        self, 
        source: Dict[str, Any], 
        candidate: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between source and candidate."""
        pass
    
    @property
    @abstractmethod
    def field_name(self) -> str:
        """Name of the field this strategy matches on."""
        pass


class LiteratureMatcher(ABC):
    """
    Abstract base class for literature matchers.
    
    Provides unified interface for different matching implementations
    (exact matching, fuzzy matching, Elasticsearch-based matching, etc.)
    """
    
    def __init__(self, dao=None):
        """
        Initialize matcher with data access object.
        
        Args:
            dao: Data access object for querying existing literature
        """
        self.dao = dao
        self.logger = logger
        
    @abstractmethod
    async def find_matches(
        self,
        source: Dict[str, Any],           # 待匹配的源数据
        match_type: MatchType,            # 匹配类型
        threshold: float = 0.8,           # 匹配阈值
        max_candidates: int = 10          # 最大候选数
    ) -> List[MatchResult]:
        """
        Find matching literature for the given source data.
        
        Args:
            source: Source literature data to match against
            match_type: Type of matching (dedup, citation, general)  
            threshold: Minimum confidence threshold for matches
            max_candidates: Maximum number of matches to return
            
        Returns:
            List of match results sorted by confidence (highest first)
        """
        pass
    
    def _normalize_source_data(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize source data for consistent matching.
        
        Args:
            source: Raw source data
            
        Returns:
            Normalized data with standardized field names and formats
        """
        normalized = {}
        
        # Extract title
        normalized["title"] = (
            source.get("title") 
            or source.get("metadata", {}).get("title")
            or ""
        ).strip()
        
        # Extract authors
        authors = source.get("authors") or source.get("metadata", {}).get("authors") or []
        if isinstance(authors, list):
            normalized["authors"] = [
                author.get("name", str(author)) if isinstance(author, dict) else str(author)
                for author in authors
            ]
        else:
            normalized["authors"] = []
            
        # Extract identifiers
        identifiers = source.get("identifiers", {})
        normalized["doi"] = (
            identifiers.get("doi") 
            or source.get("doi") 
            or source.get("metadata", {}).get("doi")
            or ""
        ).strip()
        
        normalized["arxiv_id"] = (
            identifiers.get("arxiv_id")
            or source.get("arxiv_id")
            or ""
        ).strip()
        
        # Extract year
        year = source.get("year") or source.get("metadata", {}).get("year")
        if year:
            try:
                normalized["year"] = int(year)
            except (ValueError, TypeError):
                normalized["year"] = None
        else:
            normalized["year"] = None
            
        # Extract journal
        normalized["journal"] = (
            source.get("journal")
            or source.get("metadata", {}).get("journal")
            or ""
        ).strip()
        
        return normalized
    
    def _get_match_config(self, match_type: MatchType) -> Dict[str, Any]:
        """
        Get matching configuration for the specified match type.
        
        Args:
            match_type: Type of matching
            
        Returns:
            Configuration dictionary with strategy weights and thresholds
        """
        if match_type == MatchType.DEDUPLICATION:
            return {
                "strategies": [
                    {"type": "doi", "weight": 1.0, "threshold": 1.0},      # DOI必须完全匹配
                    {"type": "title", "weight": 0.8, "threshold": 0.9},    # 标题高相似度
                    {"type": "authors", "weight": 0.6, "threshold": 0.8},  # 作者高匹配度
                ],
                "min_total_score": 0.85,  # 总分阈值
                "require_exact_doi": True
            }
        elif match_type == MatchType.CITATION:
            return {
                "strategies": [
                    {"type": "doi", "weight": 1.0, "threshold": 1.0},      # DOI精确匹配优先
                    {"type": "title", "weight": 0.7, "threshold": 0.6},    # 标题中等相似度
                    {"type": "authors", "weight": 0.5, "threshold": 0.5},  # 作者宽松匹配
                    {"type": "year", "weight": 0.3, "threshold": 0.9},     # 年份匹配
                ],
                "min_total_score": 0.6,   # 较低总分阈值
                "require_exact_doi": False
            }
        else:  # GENERAL
            return {
                "strategies": [
                    {"type": "doi", "weight": 1.0, "threshold": 1.0},
                    {"type": "title", "weight": 0.75, "threshold": 0.75},
                    {"type": "authors", "weight": 0.55, "threshold": 0.65},
                ],
                "min_total_score": 0.7,
                "require_exact_doi": False
            }

