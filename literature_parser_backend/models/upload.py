"""
文件上传相关的数据模型

定义文件上传请求和响应的数据结构。
"""

from typing import ClassVar, Dict, Any, Optional
from pydantic import BaseModel, Field, validator


class UploadRequestDTO(BaseModel):
    """文件上传请求DTO"""
    
    fileName: str = Field(..., description="文件名", min_length=1, max_length=255)
    contentType: str = Field(
        default="application/pdf",
        description="文件MIME类型",
        pattern=r"^application/pdf$|^application/octet-stream$"
    )
    fileSize: Optional[int] = Field(
        None, 
        description="文件大小（字节）", 
        ge=1, 
        le=50*1024*1024  # 50MB
    )
    userId: Optional[str] = Field(None, description="用户ID（可选）")
    
    @validator('fileName')
    def validate_filename(cls, v):
        """验证文件名"""
        from ..services.security import get_security_validator

        # 使用安全验证器进行全面检查
        security_validator = get_security_validator()
        is_valid, error_msg = security_validator.validate_filename(v)

        if not is_valid:
            raise ValueError(error_msg)

        return v
    
    @validator('contentType')
    def validate_content_type(cls, v):
        """验证内容类型"""
        allowed_types = ["application/pdf", "application/octet-stream"]
        if v not in allowed_types:
            raise ValueError(f"不支持的内容类型: {v}")
        return v
    
    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "fileName": "research_paper.pdf",
                "contentType": "application/pdf",
                "fileSize": 2048576,  # 2MB
                "userId": "user123"
            }
        }


class UploadResponseDTO(BaseModel):
    """文件上传响应DTO"""
    
    uploadUrl: str = Field(..., description="预签名上传URL")
    publicUrl: str = Field(..., description="文件的公开访问URL")
    objectKey: str = Field(..., description="对象存储键名")
    expires: int = Field(..., description="预签名URL过期时间（秒）")
    maxFileSize: int = Field(..., description="最大文件大小限制（字节）")
    
    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "uploadUrl": "https://paperparser-1330571283.cos.ap-shanghai.myqcloud.com/uploads/user123/2025/01/22/uuid.pdf?sign=xxx",
                "publicUrl": "https://paperparser-1330571283.cos.ap-shanghai.myqcloud.com/uploads/user123/2025/01/22/uuid.pdf",
                "objectKey": "uploads/user123/2025/01/22/uuid.pdf",
                "expires": 3600,
                "maxFileSize": 52428800
            }
        }


class UploadStatusDTO(BaseModel):
    """文件上传状态DTO"""
    
    objectKey: str = Field(..., description="对象存储键名")
    exists: bool = Field(..., description="文件是否存在")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    contentType: Optional[str] = Field(None, description="文件MIME类型")
    lastModified: Optional[str] = Field(None, description="最后修改时间")
    publicUrl: str = Field(..., description="公开访问URL")
    
    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "objectKey": "uploads/user123/2025/01/22/uuid.pdf",
                "exists": True,
                "size": 2048576,
                "contentType": "application/pdf",
                "lastModified": "2025-01-22T10:30:00Z",
                "publicUrl": "https://paperparser-1330571283.cos.ap-shanghai.myqcloud.com/uploads/user123/2025/01/22/uuid.pdf"
            }
        }


class UploadErrorDTO(BaseModel):
    """文件上传错误DTO"""
    
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    
    class Config:
        json_schema_extra: ClassVar[Dict[str, Any]] = {
            "example": {
                "error": "ValidationError",
                "message": "文件大小超过限制",
                "details": {
                    "maxSize": "50MB",
                    "actualSize": "75MB"
                }
            }
        }
