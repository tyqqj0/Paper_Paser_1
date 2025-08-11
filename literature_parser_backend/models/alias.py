"""
Alias-related Pydantic models.

This module contains models for the alias system that maps external identifiers
(DOI, ArXiv ID, URLs, etc.) to internal Literature IDs (LIDs).
"""

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, Field

from .common import PyObjectId


class AliasType(str, Enum):
    """Supported alias types for literature identifiers."""
    
    DOI = "doi"
    ARXIV = "arxiv"
    URL = "url"
    PDF_URL = "pdf_url"
    PMID = "pmid"
    SOURCE_PAGE = "source_page"
    TITLE = "title"  # For title-based lookups


class AliasModel(BaseModel):
    """
    Alias mapping model for external identifiers to Literature IDs.
    
    This model stores mappings between external identifiers (like DOI, URLs)
    and internal Literature IDs (LIDs), enabling fast lookups without
    requiring full literature processing.
    """
    
    id: Optional[PyObjectId] = Field(
        default=None,
        alias="_id", 
        description="MongoDB document ID"
    )
    alias_type: AliasType = Field(
        ...,
        description="Type of the alias (doi, arxiv, url, etc.)"
    )
    alias_value: str = Field(
        ...,
        description="The actual identifier value",
        index=True
    )
    lid: str = Field(
        ...,
        description="The Literature ID this alias maps to",
        index=True
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence level of this mapping (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="When this alias mapping was created"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about this alias mapping"
    )

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders: ClassVar[Dict[Any, Any]] = {
            datetime: lambda v: v.isoformat(),
            PyObjectId: str,
        }
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "_id": "507f1f77bcf86cd799439013",
                "alias_type": "doi",
                "alias_value": "10.48550/arXiv.1706.03762",
                "lid": "2017-vaswani-aiaynu-a8c4",
                "confidence": 1.0,
                "created_at": "2024-01-15T10:30:00Z",
                "metadata": {
                    "source": "literature_creation",
                    "original_request": "api_submission"
                }
            }
        }


class AliasLookupRequest(BaseModel):
    """Request model for alias lookup operations."""
    
    alias_type: AliasType = Field(..., description="Type of alias to look up")
    alias_value: str = Field(..., description="Value to look up")

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "alias_type": "doi",
                "alias_value": "10.48550/arXiv.1706.03762"
            }
        }


class AliasLookupResponse(BaseModel):
    """Response model for successful alias lookups."""
    
    lid: str = Field(..., description="The Literature ID found")
    alias: AliasModel = Field(..., description="The alias mapping details")
    resource_url: str = Field(..., description="URL to access the literature")

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "lid": "2017-vaswani-aiaynu-a8c4",
                "alias": {
                    "alias_type": "doi",
                    "alias_value": "10.48550/arXiv.1706.03762",
                    "confidence": 1.0
                },
                "resource_url": "/api/literatures/2017-vaswani-aiaynu-a8c4"
            }
        }


class AliasBatchCreateRequest(BaseModel):
    """Request model for creating multiple alias mappings at once."""
    
    lid: str = Field(..., description="The Literature ID to map to")
    mappings: Dict[AliasType, str] = Field(
        ...,
        description="Dictionary of alias_type -> alias_value mappings"
    )
    
    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "lid": "2017-vaswani-aiaynu-a8c4",
                "mappings": {
                    "doi": "10.48550/arXiv.1706.03762",
                    "arxiv": "1706.03762",
                    "url": "https://arxiv.org/abs/1706.03762"
                }
            }
        }


# Utility functions
def normalize_alias_value(alias_type: AliasType, alias_value: str) -> str:
    """
    Normalize alias values for consistent storage and lookup.
    
    Args:
        alias_type: The type of alias
        alias_value: The raw alias value
        
    Returns:
        str: Normalized alias value
    """
    if not alias_value:
        return alias_value
    
    value = alias_value.strip()
    
    if alias_type == AliasType.DOI:
        # Remove common DOI prefixes and normalize
        if value.startswith("https://doi.org/"):
            value = value[16:]
        elif value.startswith("http://doi.org/"):
            value = value[15:]
        elif value.startswith("doi:"):
            value = value[4:]
        return value.lower()
    
    elif alias_type == AliasType.ARXIV:
        # Normalize ArXiv ID format
        if value.startswith("https://arxiv.org/abs/"):
            value = value[22:]
        elif value.startswith("arxiv:"):
            value = value[6:]
        return value.lower()
    
    elif alias_type in [AliasType.URL, AliasType.PDF_URL, AliasType.SOURCE_PAGE]:
        # URLs should be case-sensitive but trimmed
        return value
    
    elif alias_type == AliasType.TITLE:
        # Titles should be normalized for better matching
        return value.lower().strip()
    
    else:
        # Default normalization
        return value.lower().strip()


def extract_aliases_from_source(source_data: Dict[str, Any]) -> Dict[AliasType, str]:
    """
    Extract all possible alias mappings from source data.
    
    Args:
        source_data: The source data dictionary from literature creation
        
    Returns:
        Dict[AliasType, str]: Dictionary of alias mappings found
    """
    aliases = {}
    
    # Extract DOI
    if doi := source_data.get("doi"):
        aliases[AliasType.DOI] = normalize_alias_value(AliasType.DOI, doi)
    
    # Extract ArXiv ID
    if arxiv_id := source_data.get("arxiv_id"):
        aliases[AliasType.ARXIV] = normalize_alias_value(AliasType.ARXIV, arxiv_id)
    
    # Extract URLs
    if url := source_data.get("url"):
        aliases[AliasType.URL] = normalize_alias_value(AliasType.URL, url)
    
    if pdf_url := source_data.get("pdf_url"):
        aliases[AliasType.PDF_URL] = normalize_alias_value(AliasType.PDF_URL, pdf_url)
    
    # Extract PMID
    if pmid := source_data.get("pmid"):
        aliases[AliasType.PMID] = normalize_alias_value(AliasType.PMID, pmid)
    
    # Extract title (for title-based lookups)
    if title := source_data.get("title"):
        aliases[AliasType.TITLE] = normalize_alias_value(AliasType.TITLE, title)
    
    return aliases
