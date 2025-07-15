"""
Task-related Pydantic models.

This module contains models for managing Celery task status
and communication between the API and background workers.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Enumeration of possible task statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"


class TaskStage(str, Enum):
    """Enumeration of processing stages for detailed progress tracking."""

    INITIALIZING = "正在初始化任务"
    EXTRACTING_IDENTIFIERS = "正在提取权威标识符"
    FETCHING_METADATA_CROSSREF = "正在从 CrossRef 获取元数据"
    FETCHING_METADATA_SEMANTIC = "正在从 Semantic Scholar 获取元数据"
    DOWNLOADING_PDF = "正在下载 PDF 文件"
    PARSING_GROBID = "正在使用 GROBID 解析 PDF"
    FETCHING_REFERENCES = "正在获取参考文献信息"
    INTEGRATING_DATA = "正在整合数据"
    SAVING_TO_DATABASE = "正在保存到数据库"
    COMPLETED = "解析完成"
    ERROR = "处理出错"


class TaskErrorInfo(BaseModel):
    """Error information when a task fails."""

    error_type: str = Field(..., description="Type/category of the error")
    error_message: str = Field(..., description="Human-readable error message")
    error_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details for debugging",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "ExternalAPIError",
                "error_message": "Failed to fetch metadata from CrossRef API",
                "error_details": {
                    "api_endpoint": "https://api.crossref.org/works/10.xxxx",
                    "http_status": 404,
                    "retry_count": 3,
                },
            },
        }


class TaskStatusDTO(BaseModel):
    """
    Task status DTO for API responses.

    Used for GET /tasks/{taskId} to provide real-time task progress
    information to the frontend.
    """

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    stage: Optional[TaskStage] = Field(None, description="Current processing stage")
    literature_id: Optional[str] = Field(
        None,
        description="Literature ID (available when status is SUCCESS)",
    )
    resource_url: Optional[str] = Field(
        None,
        description="URL to access the literature (available when status is SUCCESS)",
    )
    progress_percentage: Optional[int] = Field(
        None,
        description="Processing progress (0-100)",
        ge=0,
        le=100,
    )
    error_info: Optional[TaskErrorInfo] = Field(
        None,
        description="Error details (available when status is FAILURE)",
    )
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time",
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "task_id": "a1b2-c3d4-e5f6-g7h8",
                    "status": "processing",
                    "stage": "正在从 CrossRef 获取元数据",
                    "literature_id": None,
                    "resource_url": None,
                    "progress_percentage": 30,
                    "error_info": None,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:31:30Z",
                    "estimated_completion": "2024-01-15T10:35:00Z",
                },
                {
                    "task_id": "a1b2-c3d4-e5f6-g7h8",
                    "status": "success",
                    "stage": "解析完成",
                    "literature_id": "lit_abc123",
                    "resource_url": "/api/v1/literatures/lit_abc123",
                    "progress_percentage": 100,
                    "error_info": None,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:34:45Z",
                    "estimated_completion": None,
                },
                {
                    "task_id": "a1b2-c3d4-e5f6-g7h8",
                    "status": "failure",
                    "stage": "处理出错",
                    "literature_id": None,
                    "resource_url": None,
                    "progress_percentage": 60,
                    "error_info": {
                        "error_type": "PDFParsingError",
                        "error_message": "PDF 文件损坏或无法解析",
                        "error_details": {
                            "pdf_url": "https://example.com/broken.pdf",
                            "grobid_error": "Parsing failed after 3 attempts",
                        },
                    },
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:33:15Z",
                    "estimated_completion": None,
                },
            ],
        }


# Internal models for task management (not exposed via API)


class TaskProgressUpdate(BaseModel):
    """Internal model for updating task progress from workers."""

    task_id: str
    status: TaskStatus
    stage: Optional[TaskStage] = None
    progress_percentage: Optional[int] = None
    literature_id: Optional[str] = None
    error_info: Optional[TaskErrorInfo] = None
    estimated_completion: Optional[datetime] = None


class TaskResult(BaseModel):
    """Internal model for task completion results."""

    task_id: str
    success: bool
    literature_id: Optional[str] = None
    error_info: Optional[TaskErrorInfo] = None
    processing_time_seconds: Optional[float] = None
    stages_completed: list[TaskStage] = Field(default_factory=list)
