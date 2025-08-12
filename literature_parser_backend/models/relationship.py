"""
Literature relationship models for citation graph functionality.

This module defines data models for storing and managing citation relationships
between literatures in the 0.2 system.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    """Types of relationships between literatures."""
    
    CITES = "CITES"                    # A cites B
    CITED_BY = "CITED_BY"              # A is cited by B (reverse of CITES)
    REFERENCES = "REFERENCES"          # A references B (synonym of CITES)
    RELATED_TO = "RELATED_TO"          # A is related to B (future use)


class MatchingSource(str, Enum):
    """Sources of relationship matching."""
    
    EXACT_DOI = "exact_doi"                    # Matched by DOI
    EXACT_ARXIV = "exact_arxiv"                # Matched by ArXiv ID  
    EXACT_PMID = "exact_pmid"                  # Matched by PubMed ID
    ALIAS_SYSTEM = "alias_system"              # Matched via alias resolution
    TITLE_AUTHOR_FUZZY = "title_author_fuzzy"  # Fuzzy title+author matching
    SEMANTIC_SCHOLAR_ID = "semantic_scholar_id" # Matched by S2 paper ID
    MANUAL_VERIFICATION = "manual_verification" # Human verified
    AUTO_REFERENCE_PARSING = "auto_reference_parsing" # Automatic from references


class LiteratureRelationshipModel(BaseModel):
    """
    Model representing a relationship between two literatures.
    
    This model stores directed relationships, typically citation relationships
    where from_lid CITES to_lid.
    """
    
    from_lid: str = Field(
        ..., 
        description="LID of the literature that initiates the relationship (citer)",
        index=True
    )
    
    to_lid: str = Field(
        ..., 
        description="LID of the literature that receives the relationship (citee)",
        index=True
    )
    
    relationship_type: RelationshipType = Field(
        default=RelationshipType.CITES,
        description="Type of relationship between the literatures"
    )
    
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Confidence score of the relationship match (0.0 to 1.0)"
    )
    
    source: MatchingSource = Field(
        ...,
        description="How this relationship was discovered/matched"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata about the relationship matching"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this relationship was created"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When this relationship was last updated"
    )
    
    # For potential future use
    verified: bool = Field(
        default=False,
        description="Whether this relationship has been manually verified"
    )
    
    class Config:
        # MongoDB configuration
        collection_name = "literature_relationships"
        indexes = [
            "from_lid",
            "to_lid", 
            ("from_lid", "to_lid"),  # Compound index for relationship uniqueness
            "relationship_type",
            "confidence",
            "source"
        ]
        
        json_schema_extra = {
            "example": {
                "from_lid": "2017-vaswani-aayn-6a05",
                "to_lid": "2014-sutskever-snmtbg-a1b2", 
                "relationship_type": "CITES",
                "confidence": 0.95,
                "source": "exact_doi",
                "metadata": {
                    "matched_doi": "10.1000/example.doi",
                    "reference_index": 5,
                    "raw_reference": "Sequence to Sequence Learning..."
                },
                "created_at": "2025-08-11T10:00:00Z",
                "verified": False
            }
        }


class CitationGraphNode(BaseModel):
    """A node in the citation graph representing a literature."""
    
    lid: str = Field(..., description="Literature ID")
    title: str = Field(..., description="Literature title")
    authors: list = Field(default_factory=list, description="Author names")
    year: Optional[int] = Field(None, description="Publication year")
    journal: Optional[str] = Field(None, description="Publication venue")
    
    # Graph-specific properties
    in_degree: int = Field(default=0, description="Number of incoming citations")
    out_degree: int = Field(default=0, description="Number of outgoing citations")


class CitationGraphEdge(BaseModel):
    """An edge in the citation graph representing a citation relationship."""
    
    from_lid: str = Field(..., description="Source literature LID")
    to_lid: str = Field(..., description="Target literature LID")
    relationship_type: RelationshipType = Field(default=RelationshipType.CITES)
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: MatchingSource = Field(..., description="Matching source")


class CitationGraphResponse(BaseModel):
    """Response model for citation graph API endpoints."""
    
    nodes: list[CitationGraphNode] = Field(
        default_factory=list,
        description="Literature nodes in the graph"
    )
    
    edges: list[CitationGraphEdge] = Field(
        default_factory=list, 
        description="Citation relationships (edges) in the graph"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Graph metadata and statistics"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "nodes": [
                    {
                        "lid": "2017-vaswani-aayn-6a05",
                        "title": "Attention is All you Need",
                        "authors": ["Ashish Vaswani", "Noam Shazeer"],
                        "year": 2017,
                        "in_degree": 5000,
                        "out_degree": 41
                    }
                ],
                "edges": [
                    {
                        "from_lid": "2017-vaswani-aayn-6a05",
                        "to_lid": "2014-sutskever-snmtbg-a1b2",
                        "relationship_type": "CITES", 
                        "confidence": 0.95,
                        "source": "exact_doi"
                    }
                ],
                "metadata": {
                    "total_nodes": 10,
                    "total_edges": 25,
                    "query_time_ms": 45,
                    "subgraph_depth": 2
                }
            }
        }


