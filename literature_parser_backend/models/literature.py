"""
Literature-related Pydantic models.

This module contains:
- LiteratureModel: Main MongoDB document schema
- API DTOs for literature operations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import PyObjectId

# ===============================
# Core Data Models
# ===============================


class AuthorModel(BaseModel):
    """Author information within a literature."""

    name: str = Field(..., description="Author name")
    s2_id: Optional[str] = Field(None, description="Semantic Scholar Author ID")

    class Config:
        json_schema_extra = {
            "example": {"name": "Ashish Vaswani", "s2_id": "1738948"},
        }


class IdentifiersModel(BaseModel):
    """Collection of authoritative identifiers for a literature."""

    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    arxiv_id: Optional[str] = Field(None, description="ArXiv identifier")
    fingerprint: Optional[str] = Field(None, description="Content-based fingerprint")

    class Config:
        json_schema_extra = {
            "example": {
                "doi": "10.48550/arXiv.1706.03762",
                "arxiv_id": "1706.03762",
                "fingerprint": "vaswani2017attention_sha256",
            },
        }


class MetadataModel(BaseModel):
    """Literature metadata information."""

    title: str = Field(..., description="Literature title")
    authors: List[AuthorModel] = Field(
        default_factory=list,
        description="List of authors",
    )
    year: Optional[int] = Field(None, description="Publication year")
    journal: Optional[str] = Field(None, description="Journal or venue name")
    abstract: Optional[str] = Field(None, description="Literature abstract")
    keywords: List[str] = Field(default_factory=list, description="Keywords or tags")
    source_priority: List[str] = Field(
        default_factory=list,
        description="Data sources in order of priority used",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Attention Is All You Need",
                "authors": [
                    {"name": "Ashish Vaswani"},
                    {"name": "Noam Shazeer"},
                ],
                "year": 2017,
                "journal": "Advances in Neural Information Processing Systems",
                "abstract": "The dominant sequence transduction models...",
                "keywords": ["transformer", "nlp", "attention"],
                "source_priority": ["CrossRef API", "GROBID"],
            },
        }


class ContentModel(BaseModel):
    """Literature content and parsing information."""

    pdf_url: Optional[str] = Field(default=None, description="URL to the PDF file")
    source_page_url: Optional[str] = Field(default=None, description="Original source page URL")
    parsed_fulltext: Optional[Dict[str, Any]] = Field(
        default=None,
        description="GROBID parsed fulltext (large JSON object, excluded from summary APIs)",
    )
    sources_tried: List[str] = Field(
        default_factory=list,
        description="List of URLs or methods tried for content fetching.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pdf_url": "https://my-oss.com/1706.03762.pdf",
                "source_page_url": "https://arxiv.org/abs/1706.03762",
                "parsed_fulltext": {"note": "Large JSON object from GROBID"},
                "sources_tried": [
                    "user_pdf_url: https://example.com/paper.pdf",
                    "arxiv: https://arxiv.org/pdf/1706.03762.pdf",
                ],
            },
        }


class ReferenceModel(BaseModel):
    """Single reference within a literature."""

    raw_text: str = Field(..., description="Original raw reference string")
    parsed: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured parsed reference data",
    )
    source: str = Field(..., description="Source of this reference parsing")

    class Config:
        json_schema_extra = {
            "example": {
                "raw_text": "Y. Bengio, et al. A neural probabilistic language model. JMLR, 2003.",
                "parsed": {
                    "title": "A neural probabilistic language model",
                    "year": 2003,
                    "authors": [{"full_name": "Yoshua Bengio"}],
                },
                "source": "Semantic Scholar API",
            },
        }


class TaskInfoModel(BaseModel):
    """Task information associated with this literature."""

    task_id: Optional[str] = Field(None, description="Associated Celery task ID")
    status: Optional[str] = Field(None, description="Task processing status")
    created_at: Optional[datetime] = Field(None, description="Task creation time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")


# ===============================
# Main MongoDB Document Model
# ===============================


class LiteratureModel(BaseModel):
    """
    Main literature model representing a MongoDB document.

    This model corresponds to documents in the 'literatures' collection
    and contains all information about a parsed literature.
    """

    id: Optional[PyObjectId] = Field(
        default=None,
        alias="_id",
        description="MongoDB document ID",
    )
    user_id: Optional[PyObjectId] = Field(
        None,
        description="ID of the user who created this literature",
    )
    task_info: Optional[TaskInfoModel] = Field(
        None,
        description="Information about the parsing task",
    )
    identifiers: IdentifiersModel = Field(..., description="Authoritative identifiers")
    metadata: MetadataModel = Field(..., description="Literature metadata")
    content: ContentModel = Field(
        default_factory=lambda: ContentModel(), description="Content and parsing data"
    )
    references: List[ReferenceModel] = Field(
        default_factory=list,
        description="List of parsed references",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Last update timestamp",
    )
    raw_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw data from various sources, for debugging.",
    )

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {datetime: lambda v: v.isoformat(), PyObjectId: str}
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": "507f1f77bcf86cd799439012",
                "identifiers": {
                    "doi": "10.48550/arXiv.1706.03762",
                    "arxiv_id": "1706.03762",
                },
                "metadata": {
                    "title": "Attention Is All You Need",
                    "authors": [{"name": "Ashish Vaswani"}],
                    "year": 2017,
                },
                "content": {"pdf_url": "https://arxiv.org/pdf/1706.03762.pdf"},
                "references": [],
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            },
        }


# ===============================
# API Request/Response DTOs
# ===============================


class LiteratureSourceDTO(BaseModel):
    """Source information for creating a literature."""

    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    url: Optional[str] = Field(None, description="URL to the literature (ArXiv, etc.)")
    pdf_url: Optional[str] = Field(None, description="Direct URL to PDF file")
    title: Optional[str] = Field(
        None,
        description="Literature title (for deduplication)",
    )
    authors: Optional[List[str]] = Field(None, description="List of author names")

    class Config:
        json_schema_extra = {
            "example": {
                "doi": "10.48550/arXiv.1706.03762",
                "url": "https://arxiv.org/abs/1706.03762",
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
            },
        }


class LiteratureCreateDTO(BaseModel):
    """Request DTO for creating a new literature."""

    # 支持直接传入字段或通过source对象
    source: Optional[LiteratureSourceDTO] = Field(
        None,
        description="Source information for the literature",
    )

    # 直接字段支持（向后兼容）
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    arxiv_id: Optional[str] = Field(None, description="ArXiv identifier")
    url: Optional[str] = Field(None, description="URL to the literature")
    pdf_url: Optional[str] = Field(None, description="Direct URL to PDF file")
    title: Optional[str] = Field(None, description="Literature title")
    authors: Optional[List[str]] = Field(None, description="List of author names")

    def get_effective_values(self) -> Dict[str, Any]:
        """Get effective values, prioritizing direct fields over source fields."""
        if self.source:
            return {
                "doi": self.doi or self.source.doi,
                "arxiv_id": self.arxiv_id,  # source doesn't have arxiv_id
                "url": self.url or self.source.url,
                "pdf_url": self.pdf_url or self.source.pdf_url,
                "title": self.title or self.source.title,
                "authors": self.authors or self.source.authors,
            }
        else:
            return {
                "doi": self.doi,
                "arxiv_id": self.arxiv_id,
                "url": self.url,
                "pdf_url": self.pdf_url,
                "title": self.title,
                "authors": self.authors,
            }

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "doi": "10.48550/arXiv.1706.03762",
                "url": "https://arxiv.org/abs/1706.03762",
            },
        }


class LiteratureCreatedResponseDTO(BaseModel):
    """Response DTO when literature already exists."""

    literature_id: str = Field(..., description="ID of the existing literature")
    resource_url: str = Field(..., description="URL to access the literature")

    class Config:
        json_schema_extra = {
            "example": {
                "literature_id": "lit_abc123",
                "resource_url": "/api/v1/literatures/lit_abc123",
            },
        }


class LiteratureTaskCreatedResponseDTO(BaseModel):
    """Response DTO when a new parsing task is created."""

    task_id: str = Field(..., description="ID of the created parsing task")
    status_url: str = Field(..., description="URL to check task status")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "a1b2-c3d4-e5f6-g7h8",
                "status_url": "/api/v1/tasks/a1b2-c3d4-e5f6-g7h8",
            },
        }


class LiteratureSummaryDTO(BaseModel):
    """
    Summary DTO for literature (excludes large fulltext content).

    Used for GET /literatures/{id} - contains metadata and references
    but excludes the potentially large parsed_fulltext.
    """

    id: str = Field(..., description="Literature ID")
    identifiers: IdentifiersModel = Field(..., description="Authoritative identifiers")
    metadata: MetadataModel = Field(..., description="Literature metadata")
    content: Dict[str, Any] = Field(
        ...,
        description="Content info (without parsed_fulltext)",
    )
    references: List[ReferenceModel] = Field(..., description="List of references")
    task_info: Optional["TaskInfoModel"] = Field(None, description="Task information")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # 便利字段 - 从metadata中提取的信息，便于前端使用
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        """
        Populate convenience fields after the model is initialized.
        This is a Pydantic V2 feature that replaces @root_validator.
        """
        if self.metadata:
            self.title = self.metadata.title
            self.authors = [author.name for author in self.metadata.authors]
            self.year = self.metadata.year
            self.journal = self.metadata.journal
        if self.identifiers:
            self.doi = self.identifiers.doi

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        # This is a simplified conversion, you might want to customize it
        return self.model_dump(by_alias=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LiteratureSummaryDTO":
        """Create a model from a dictionary."""
        return cls(**data)


class LiteratureFulltextDTO(BaseModel):
    """
    Fulltext DTO for literature parsed content.

    Used for GET /literatures/{id}/fulltext - returns the large
    GROBID parsed content structure.
    """

    literature_id: str = Field(..., description="Literature ID")
    parsed_fulltext: Optional[Dict[str, Any]] = Field(
        None,
        description="Complete GROBID parsed content",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "literature_id": "507f1f77bcf86cd799439011",
                "parsed_fulltext": {"note": "Large JSON object from GROBID"},
            }
        }


# ===============================
# Utility Functions
# ===============================


def literature_to_summary_dto(literature: LiteratureModel) -> LiteratureSummaryDTO:
    """Convert a LiteratureModel to a LiteratureSummaryDTO."""
    # The conversion is now primarily handled by the DTO's `model_post_init`.
    # We just need to pass the required fields.
    summary_data = literature.model_dump(
        include={
            "id",
            "identifiers",
            "metadata",
            "content",
            "references",
            "task_info",
            "created_at",
            "updated_at",
        }
    )
    # Pydantic v2 needs the 'id' as a string.
    summary_data["id"] = str(summary_data["id"])

    # The 'content' field in the DTO should not contain the large 'parsed_fulltext'.
    if "parsed_fulltext" in summary_data.get("content", {}):
        del summary_data["content"]["parsed_fulltext"]

    return LiteratureSummaryDTO(**summary_data)


def literature_to_fulltext_dto(literature: LiteratureModel) -> LiteratureFulltextDTO:
    """Convert a LiteratureModel to a LiteratureFulltextDTO."""
    return LiteratureFulltextDTO(
        literature_id=str(literature.id),
        parsed_fulltext=literature.content.parsed_fulltext,
    )
