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
    LiteratureCreateRequestDTO,
    LiteratureFulltextDTO,
    LiteratureModel,
    LiteratureSourceDTO,
    LiteratureSummaryDTO,
    MetadataModel,
    ReferenceModel,
    TaskInfoModel,
)
from .task import TaskStatus, TaskStatusDTO

__all__ = [
    "LiteratureModel",
    "LiteratureCreateRequestDTO",
    "LiteratureSourceDTO",
    "LiteratureSummaryDTO",
    "LiteratureFulltextDTO",
    "AuthorModel",
    "IdentifiersModel",
    "MetadataModel",
    "ContentModel",
    "ReferenceModel",
    "TaskInfoModel",
    "TaskStatus",
    "TaskStatusDTO",
    "PyObjectId",
]
