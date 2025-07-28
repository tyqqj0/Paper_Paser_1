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


class ComponentStatus(str, Enum):
    """组件状态枚举"""
    PENDING = "pending"           # 等待开始
    PROCESSING = "processing"     # 正在处理
    SUCCESS = "success"          # 处理成功
    FAILED = "failed"            # 处理失败
    SKIPPED = "skipped"          # 已跳过
    WAITING = "waiting"          # 等待依赖


class ComponentDetail(BaseModel):
    """单个组件的详细状态信息"""

    status: ComponentStatus = Field(
        default=ComponentStatus.PENDING,
        description="组件状态"
    )
    stage: str = Field(
        default="等待开始",
        description="详细阶段描述，如'正在从CrossRef获取元数据'"
    )
    progress: int = Field(
        default=0,
        description="进度百分比 0-100",
        ge=0, le=100
    )
    started_at: Optional[datetime] = Field(
        None,
        description="组件开始处理时间"
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="组件完成处理时间"
    )
    error_info: Optional[Dict[str, Any]] = Field(
        None,
        description="错误详情（如果失败）"
    )
    source: Optional[str] = Field(
        None,
        description="数据来源，如'CrossRef', 'Semantic Scholar'"
    )
    attempts: int = Field(
        default=0,
        description="尝试次数"
    )
    max_attempts: int = Field(
        default=3,
        description="最大尝试次数"
    )

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


class LiteratureComponentStatus(BaseModel):
    """文献各组件的详细状态跟踪"""

    metadata: ComponentDetail = Field(
        default_factory=ComponentDetail,
        description="元数据获取状态"
    )
    content: ComponentDetail = Field(
        default_factory=ComponentDetail,
        description="内容获取和解析状态"
    )
    references: ComponentDetail = Field(
        default_factory=ComponentDetail,
        description="参考文献获取状态"
    )

    def get_overall_progress(self) -> int:
        """计算整体进度（三个组件的平均值）"""
        total_progress = (
            self.metadata.progress + self.content.progress + self.references.progress
        )
        return total_progress // 3

    def get_critical_components_status(self) -> Dict[str, str]:
        """Get status of critical components (metadata + references)."""
        return {"metadata": self.metadata.status, "references": self.references.status}


class LiteratureProcessingStatus(BaseModel):
    """文献处理的完整状态信息"""

    literature_id: str = Field(..., description="文献ID")
    overall_status: str = Field(..., description="整体状态: processing/completed/failed")
    overall_progress: int = Field(
        default=0,
        description="整体进度 0-100",
        ge=0, le=100
    )

    # 使用组合而不是重复字段
    component_status: LiteratureComponentStatus = Field(
        default_factory=LiteratureComponentStatus,
        description="各组件的详细状态"
    )

    # 时间信息
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TaskExecutionStatus(str, Enum):
    """任务执行状态 - 用于前端轮询控制"""
    PENDING = "pending"        # 任务等待执行 - 继续轮询
    PROCESSING = "processing"  # 任务正在执行 - 继续轮询
    COMPLETED = "completed"    # 任务执行完成 - 停止轮询
    FAILED = "failed"         # 任务执行失败 - 停止轮询


class TaskResultType(str, Enum):
    """任务结果类型 - 用于结果类型标识和调试"""
    CREATED = "created"       # 创建了新文献
    DUPLICATE = "duplicate"   # 发现重复文献



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

    # URL验证错误相关字段（新增）
    error_category: Optional[str] = Field(
        None,
        description="错误类别: url_validation/metadata_fetch/content_parse/references_fetch"
    )
    url_validation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="URL验证详细信息"
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
    """统一的任务状态响应模型"""

    # 任务信息（轮询控制用）
    task_id: str = Field(..., description="Celery任务ID")
    execution_status: TaskExecutionStatus = Field(..., description="任务执行状态")
    result_type: Optional[TaskResultType] = Field(
        None,
        description="任务结果类型"
    )

    # 文献信息（详细展示用）
    literature_id: Optional[str] = Field(
        None,
        description="关联的文献ID"
    )
    literature_status: Optional[LiteratureProcessingStatus] = Field(
        None,
        description="文献处理的详细状态"
    )

    # 向后兼容字段（映射到execution_status）
    status: str = Field(..., description="任务状态（兼容性字段）")

    # 简化的进度信息（从literature_status聚合）
    overall_progress: int = Field(
        default=0,
        description="整体进度",
        ge=0, le=100
    )
    current_stage: Optional[str] = Field(
        None,
        description="当前阶段描述"
    )

    # URL验证相关字段（新增）
    url_validation_status: Optional[str] = Field(
        None,
        description="URL验证状态: success/failed/skipped"
    )
    url_validation_error: Optional[str] = Field(
        None,
        description="URL验证错误信息"
    )
    original_url: Optional[str] = Field(
        None,
        description="原始提交的URL"
    )

    # 错误信息
    error_info: Optional[TaskErrorInfo] = Field(
        None,
        description="错误详情"
    )

    # 兼容性字段
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="额外详情信息"
    )
    resource_url: Optional[str] = Field(
        None,
        description="文献访问URL"
    )






# Internal models for task management (not exposed via API)


class TaskProgressUpdate(BaseModel):
    """Internal model for updating task progress from workers."""

    task_id: str
    execution_status: TaskExecutionStatus
    current_stage: Optional[str] = None
    progress: Optional[int] = None
    literature_id: Optional[str] = None
    error_info: Optional[TaskErrorInfo] = None


class TaskResult(BaseModel):
    """Internal model for task completion results."""

    task_id: str
    execution_status: TaskExecutionStatus
    result_type: Optional[TaskResultType] = None
    literature_id: Optional[str] = None
    error_info: Optional[TaskErrorInfo] = None
    processing_time_seconds: Optional[float] = None
