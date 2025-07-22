"""
文件上传API端点

提供文件上传的预签名URL生成和文件状态查询功能。
支持安全的前端直传到腾讯云COS。
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from loguru import logger

from literature_parser_backend.models.upload import (
    UploadRequestDTO,
    UploadResponseDTO,
    UploadStatusDTO,
    UploadErrorDTO
)
from literature_parser_backend.services.cos import get_cos_service, extract_object_key_from_url
from literature_parser_backend.services.security import get_security_validator
from literature_parser_backend.settings import Settings

router = APIRouter(prefix="/upload", tags=["文件上传"])

# 获取设置实例
settings = Settings()





@router.post(
    "/request-url",
    response_model=UploadResponseDTO,
    summary="请求文件上传预签名URL",
    description="生成用于前端直传到COS的预签名URL和公开访问URL",
    status_code=status.HTTP_200_OK,
)
async def request_upload_url(request: Request) -> UploadResponseDTO:
    """
    请求文件上传预签名URL

    前端使用此接口获取预签名URL，然后直接上传文件到COS。

    Args:
        request: HTTP请求对象

    Returns:
        包含预签名URL和公开URL的响应

    Raises:
        HTTPException: 当参数验证失败或生成URL失败时
    """
    try:
        # 手动解析JSON数据
        request_data = await request.json()

        # 手动验证必需字段
        if "fileName" not in request_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ValidationError",
                    "message": "fileName字段是必需的"
                }
            )

        filename = request_data["fileName"]
        content_type = request_data.get("contentType", "application/pdf")
        file_size = request_data.get("fileSize")
        user_id = request_data.get("userId")

        logger.info("收到上传URL请求: {}, 大小: {}", filename, file_size)

        # 安全验证
        security_validator = get_security_validator()
        is_valid, errors = security_validator.validate_upload_request(
            filename=filename,
            mime_type=content_type,
            file_size=file_size
        )

        if not is_valid:
            logger.warning("上传请求安全验证失败: {}", errors)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "SecurityValidationError",
                    "message": "; ".join(errors)
                }
            )

        # 获取COS服务实例
        cos_service = get_cos_service()

        # 生成预签名URL
        result = cos_service.generate_presigned_upload_url(
            filename=filename,
            content_type=content_type,
            user_id=user_id,
            file_size=file_size
        )

        # 构建响应
        response = UploadResponseDTO(
            uploadUrl=result["uploadUrl"],
            publicUrl=result["publicUrl"],
            objectKey=result["objectKey"],
            expires=result["expires"],
            maxFileSize=settings.upload_max_file_size
        )

        logger.info("生成上传URL成功: {}", result['objectKey'])
        return response
        
    except ValueError as e:
        logger.warning("上传请求参数错误: {}", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e)
            }
        )
    except HTTPException:
        # 重新抛出HTTP异常，不要被通用异常处理器捕获
        raise
    except RuntimeError as e:
        logger.error("生成上传URL失败: {}", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "生成上传URL失败，请稍后重试"
            }
        )
    except Exception as e:
        logger.error("未知错误: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "UnknownError",
                "message": "服务器内部错误"
            }
        )


@router.get(
    "/status",
    response_model=UploadStatusDTO,
    summary="查询文件上传状态",
    description="通过公开URL或对象键名查询文件是否已成功上传",
)
async def check_upload_status(
    public_url: Optional[str] = Query(None, description="文件的公开访问URL"),
    object_key: Optional[str] = Query(None, description="对象存储键名")
) -> UploadStatusDTO:
    """
    查询文件上传状态
    
    可以通过公开URL或对象键名查询文件是否已成功上传到COS。
    
    Args:
        public_url: 文件的公开访问URL
        object_key: 对象存储键名
        
    Returns:
        文件状态信息
        
    Raises:
        HTTPException: 当参数错误或查询失败时
    """
    try:
        if not public_url and not object_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ValidationError",
                    "message": "必须提供 public_url 或 object_key 参数"
                }
            )
        
        # 获取COS服务实例
        cos_service = get_cos_service()
        
        # 如果提供了public_url，提取object_key
        if public_url and not object_key:
            object_key = extract_object_key_from_url(public_url, settings.cos_domain)
            if not object_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "ValidationError",
                        "message": "无法从URL中提取对象键名"
                    }
                )
        
        # 检查文件是否存在
        exists = cos_service.check_object_exists(object_key)
        
        # 获取文件信息
        file_info = None
        if exists:
            file_info = cos_service.get_object_info(object_key)
        
        # 生成公开URL（如果没有提供）
        if not public_url:
            from urllib.parse import quote
            public_url = "https://" + settings.cos_domain + "/" + quote(object_key)
        
        # 构建响应
        response = UploadStatusDTO(
            objectKey=object_key,
            exists=exists,
            size=file_info.get("size") if file_info else None,
            contentType=file_info.get("content_type") if file_info else None,
            lastModified=file_info.get("last_modified") if file_info else None,
            publicUrl=public_url
        )
        
        logger.info("查询文件状态: {}, 存在: {}", object_key, exists)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("查询文件状态失败: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "查询文件状态失败"
            }
        )


@router.delete(
    "/file",
    summary="删除上传的文件",
    description="删除COS中的文件（仅限管理员或文件所有者）",
)
async def delete_uploaded_file(
    public_url: Optional[str] = Query(None, description="文件的公开访问URL"),
    object_key: Optional[str] = Query(None, description="对象存储键名")
) -> JSONResponse:
    """
    删除上传的文件
    
    Args:
        public_url: 文件的公开访问URL
        object_key: 对象存储键名
        
    Returns:
        删除结果
    """
    try:
        if not public_url and not object_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "ValidationError",
                    "message": "必须提供 public_url 或 object_key 参数"
                }
            )
        
        # 获取COS服务实例
        cos_service = get_cos_service()
        
        # 如果提供了public_url，提取object_key
        if public_url and not object_key:
            object_key = extract_object_key_from_url(public_url, settings.cos_domain)
            if not object_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "ValidationError",
                        "message": "无法从URL中提取对象键名"
                    }
                )
        
        # 删除文件
        success = cos_service.delete_object(object_key)
        
        if success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "文件删除成功",
                    "objectKey": object_key
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "DeleteError",
                    "message": "文件删除失败"
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除文件失败: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "删除文件失败"
            }
        )
