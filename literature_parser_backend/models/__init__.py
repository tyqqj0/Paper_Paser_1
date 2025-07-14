"""
Models package for literature parser backend.

This package contains all Pydantic models for:
- MongoDB document schemas
- API request/response DTOs
- Internal data transfer objects
"""

from .common import PyObjectId
from .literature import (
    AuthorModel,
    ContentModel,
    IdentifiersModel,
    LiteratureCreateDTO,
    LiteratureFulltextDTO,
    LiteratureModel,
    LiteratureSourceDTO,
    LiteratureSummaryDTO,
    MetadataModel,
    ReferenceModel,
    TaskInfoModel,
)
from .task import TaskStatusDTO

__all__ = [
    "LiteratureModel",
    "LiteratureCreateDTO",
    "LiteratureSourceDTO",
    "LiteratureSummaryDTO",
    "LiteratureFulltextDTO",
    "AuthorModel",
    "IdentifiersModel",
    "MetadataModel",
    "ContentModel",
    "ReferenceModel",
    "TaskInfoModel",
    "TaskStatusDTO",
    "PyObjectId",
]
