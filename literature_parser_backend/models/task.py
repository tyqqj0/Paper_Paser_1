"""
Task-related Pydantic models.

This module contains models for managing Celery task status
and communication between the API and background workers.
"""

from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field

# ===============================
# Core Data Models for Task Status
# ===============================


class EnhancedComponentStatus(BaseModel):
    """Enhanced status tracking for a single component with detailed information."""

    status: str = Field(
        default="pending",
        description="Component status (pending/processing/success/failed/waiting/skipped)",
    )
    stage: str = Field(default="等待开始", description="Detailed stage description")
    progress: int = Field(
        default=0, description="Progress percentage (0-100)", ge=0, le=100,
    )
    error_info: Optional[Dict[str, Any]] = Field(
        None, description="Error details if failed",
    )
    started_at: Optional[datetime] = Field(
        None, description="When component processing started",
    )
    completed_at: Optional[datetime] = Field(
        None, description="When component processing completed",
    )
    dependencies_met: bool = Field(
        default=True, description="Whether dependencies are satisfied",
    )
    next_action: Optional[str] = Field(
        None, description="Description of next action to be taken",
    )
    source: Optional[str] = Field(
        None, description="Data source that succeeded (e.g., 'CrossRef API')",
    )
    attempts: int = Field(default=0, description="Number of attempts made")
    max_attempts: int = Field(default=3, description="Maximum attempts allowed")

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "status": "success",
                "stage": "元数据获取成功",
                "progress": 100,
                "error_info": None,
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:31:00Z",
                "dependencies_met": True,
                "next_action": None,
                "source": "CrossRef API",
                "attempts": 1,
                "max_attempts": 3,
            },
        }


class ComponentStatus(BaseModel):
    """Enhanced component status tracking with detailed information for each component."""

    metadata: EnhancedComponentStatus = Field(
        default_factory=EnhancedComponentStatus,
        description="Enhanced metadata fetching status",
    )
    content: EnhancedComponentStatus = Field(
        default_factory=EnhancedComponentStatus,
        description="Enhanced content fetching and parsing status",
    )
    references: EnhancedComponentStatus = Field(
        default_factory=EnhancedComponentStatus,
        description="Enhanced references fetching status",
    )

    def get_overall_progress(self) -> int:
        """Calculate overall progress as average of all components."""
        total_progress = (
            self.metadata.progress + self.content.progress + self.references.progress
        )
        return total_progress // 3

    def get_critical_components_status(self) -> Dict[str, str]:
        """Get status of critical components (metadata + references)."""
        return {"metadata": self.metadata.status, "references": self.references.status}


class LegacyComponentStatus(BaseModel):
    """Legacy simple component status for backward compatibility."""

    metadata: str = Field(default="pending", description="Status of metadata fetching")
    content: str = Field(
        default="pending",
        description="Status of content fetching and parsing",
    )
    references: str = Field(
        default="pending",
        description="Status of references fetching",
    )


class TaskStatus(str, Enum):
    """Enum for the overall status of a task."""

    """Enumeration of possible task statuses."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"


class ComponentStage(str, Enum):
    """Enumeration of detailed processing stages for each component."""

    # Common stages
    PENDING = "等待开始"
    INITIALIZING = "正在初始化"
    PROCESSING = "正在处理"
    SUCCESS = "处理成功"
    FAILED = "处理失败"
    SKIPPED = "已跳过"
    WAITING = "等待依赖"

    # Metadata stages
    METADATA_PENDING = "等待获取元数据"
    METADATA_CROSSREF = "正在从CrossRef获取元数据"
    METADATA_SEMANTIC = "正在从Semantic Scholar获取元数据"
    METADATA_GROBID_FALLBACK = "使用GROBID作为元数据后备方案"
    METADATA_SUCCESS = "元数据获取成功"
    METADATA_FAILED = "元数据获取失败"

    # Content stages
    CONTENT_PENDING = "等待获取内容"
    CONTENT_DOWNLOAD_USER = "正在下载用户提供的PDF"
    CONTENT_DOWNLOAD_ARXIV = "正在下载ArXiv PDF"
    CONTENT_DOWNLOAD_UNPAYWALL = "正在通过Unpaywall获取PDF"
    CONTENT_PARSE_GROBID = "正在使用GROBID解析PDF"
    CONTENT_SUCCESS = "内容获取成功"
    CONTENT_SKIPPED = "内容获取已跳过"
    CONTENT_FAILED = "内容获取失败"

    # References stages
    REFERENCES_PENDING = "等待获取参考文献"
    REFERENCES_WAITING_CONTENT = "等待内容获取完成"
    REFERENCES_API_SEMANTIC = "正在从Semantic Scholar获取参考文献"
    REFERENCES_GROBID_PARSE = "正在使用GROBID解析参考文献"
    REFERENCES_SUCCESS = "参考文献获取成功"
    REFERENCES_FAILED = "参考文献获取失败"


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
        description="Detailed error information (e.g., API responses)",
    )

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
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
    """Enhanced data transfer object for task status queries."""

    task_id: str = Field(..., description="The Celery task ID")
    status: str = Field(..., description="Overall status of the task")
    result: Optional[Any] = Field(
        None,
        description="The result of the task, if completed.",
    )

    # Enhanced granular status and progress
    component_status: ComponentStatus = Field(
        default_factory=ComponentStatus,
        description="Enhanced granular status of each processing component",
    )
    overall_progress: int = Field(
        default=0,
        description="Overall processing progress (0-100)",
        ge=0,
        le=100,
    )
    current_stage: Optional[str] = Field(
        None,
        description="Current processing stage description",
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional detailed progress information",
    )
    literature_id: Optional[str] = Field(
        None,
        description="Literature ID (available when processing starts or completes)",
    )
    resource_url: Optional[str] = Field(
        None,
        description="URL to access the literature (available when status is SUCCESS)",
    )
    error_info: Optional[TaskErrorInfo] = Field(
        None,
        description="Error details (available when status is FAILURE)",
    )

    # Enhanced timestamps and progress tracking
    created_at: Optional[datetime] = Field(None, description="Task creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    estimated_completion: Optional[datetime] = Field(
        None,
        description="Estimated completion time",
    )

    # Dependency tracking
    dependencies: Optional[Dict[str, bool]] = Field(
        None,
        description="Status of component dependencies",
    )
    next_actions: Optional[List[str]] = Field(
        None,
        description="List of next actions to be performed",
    )

    def model_post_init(self, __context: Any) -> None:
        """Auto-calculate fields after model initialization."""
        # Calculate overall progress from component status
        if self.component_status:
            self.overall_progress = self.component_status.get_overall_progress()

        # Set current stage based on active component
        if self.component_status:
            active_stages = []
            if self.component_status.metadata.status == "processing":
                active_stages.append(self.component_status.metadata.stage)
            if self.component_status.content.status == "processing":
                active_stages.append(self.component_status.content.stage)
            if self.component_status.references.status == "processing":
                active_stages.append(self.component_status.references.stage)

            if active_stages:
                self.current_stage = "; ".join(active_stages)
            elif self.status == "success":
                self.current_stage = "处理完成"
            elif self.status == "failed":
                self.current_stage = "处理失败"

        # Collect next actions
        if self.component_status:
            next_actions = []
            if self.component_status.metadata.next_action:
                next_actions.append(self.component_status.metadata.next_action)
            if self.component_status.content.next_action:
                next_actions.append(self.component_status.content.next_action)
            if self.component_status.references.next_action:
                next_actions.append(self.component_status.references.next_action)
            self.next_actions = next_actions if next_actions else None

    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
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
