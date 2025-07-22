"""
腾讯云COS对象存储服务

提供文件上传的预签名URL生成和文件管理功能。
支持安全的前端直传和后端文件访问。
"""

import hashlib
import mimetypes
import os
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import quote

from loguru import logger
from qcloud_cos import CosConfig, CosS3Client

from ..settings import Settings


class COSService:
    """腾讯云COS对象存储服务类"""
    
    def __init__(self, settings: Optional[Settings] = None):
        """初始化COS服务"""
        self.settings = settings or Settings()
        
        # 验证必需的配置
        if not self.settings.cos_secret_id or not self.settings.cos_secret_key:
            raise ValueError("COS SecretId and SecretKey are required")
        
        # 初始化COS客户端
        config = CosConfig(
            Region=self.settings.cos_region,
            SecretId=self.settings.cos_secret_id,
            SecretKey=self.settings.cos_secret_key,
            Scheme='https'  # 使用HTTPS
        )
        self.client = CosS3Client(config)
        
        logger.info(f"COS服务初始化完成: Region={self.settings.cos_region}, Bucket={self.settings.cos_bucket}")
    
    def generate_object_key(self, filename: str, user_id: Optional[str] = None) -> str:
        """
        生成对象存储的键名
        
        Args:
            filename: 原始文件名
            user_id: 用户ID（可选）
            
        Returns:
            生成的对象键名
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(filename)
        if not ext:
            ext = '.pdf'  # 默认为PDF
        
        # 生成唯一标识符
        unique_id = str(uuid.uuid4())
        
        # 生成时间戳路径
        now = datetime.now()
        date_path = now.strftime("%Y/%m/%d")
        
        # 构建对象键名
        if user_id:
            object_key = f"uploads/{user_id}/{date_path}/{unique_id}{ext}"
        else:
            object_key = f"uploads/anonymous/{date_path}/{unique_id}{ext}"
        
        return object_key
    
    def validate_file_info(self, filename: str, content_type: str, file_size: Optional[int] = None) -> Tuple[bool, str]:
        """
        验证文件信息
        
        Args:
            filename: 文件名
            content_type: 文件MIME类型
            file_size: 文件大小（字节）
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件扩展名
        _, ext = os.path.splitext(filename.lower())
        if ext not in self.settings.upload_allowed_extensions:
            return False, f"不支持的文件类型: {ext}。支持的类型: {', '.join(self.settings.upload_allowed_extensions)}"
        
        # 检查MIME类型
        expected_mime = mimetypes.guess_type(filename)[0]
        if content_type != expected_mime and content_type != "application/pdf":
            logger.warning(f"MIME类型不匹配: 期望 {expected_mime}, 实际 {content_type}")
        
        # 检查文件大小
        if file_size and file_size > self.settings.upload_max_file_size:
            max_size_mb = self.settings.upload_max_file_size / (1024 * 1024)
            return False, f"文件大小超过限制: {file_size} bytes > {max_size_mb:.1f}MB"
        
        return True, ""
    
    def generate_presigned_upload_url(
        self, 
        filename: str, 
        content_type: str = "application/pdf",
        user_id: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> Dict[str, str]:
        """
        生成预签名上传URL
        
        Args:
            filename: 文件名
            content_type: 文件MIME类型
            user_id: 用户ID（可选）
            file_size: 文件大小（可选，用于验证）
            
        Returns:
            包含uploadUrl和publicUrl的字典
        """
        # 验证文件信息
        is_valid, error_msg = self.validate_file_info(filename, content_type, file_size)
        if not is_valid:
            raise ValueError(error_msg)
        
        # 生成对象键名
        object_key = self.generate_object_key(filename, user_id)
        
        try:
            # 生成预签名上传URL
            presigned_url = self.client.get_presigned_url(
                Method='PUT',
                Bucket=self.settings.cos_bucket,
                Key=object_key,
                Expired=self.settings.upload_presigned_url_expires,
                Params={
                    'Content-Type': content_type
                }
            )
            
            # 生成公开访问URL
            public_url = f"https://{self.settings.cos_domain}/{quote(object_key)}"
            
            logger.info(f"生成预签名URL成功: {object_key}")
            
            return {
                "uploadUrl": presigned_url,
                "publicUrl": public_url,
                "objectKey": object_key,
                "expires": self.settings.upload_presigned_url_expires
            }
            
        except Exception as e:
            logger.error(f"生成预签名URL失败: {e}")
            raise RuntimeError(f"生成预签名URL失败: {str(e)}")
    
    def check_object_exists(self, object_key: str) -> bool:
        """
        检查对象是否存在
        
        Args:
            object_key: 对象键名
            
        Returns:
            对象是否存在
        """
        try:
            self.client.head_object(
                Bucket=self.settings.cos_bucket,
                Key=object_key
            )
            return True
        except Exception:
            return False
    
    def get_object_info(self, object_key: str) -> Optional[Dict[str, any]]:
        """
        获取对象信息
        
        Args:
            object_key: 对象键名
            
        Returns:
            对象信息字典或None
        """
        try:
            response = self.client.head_object(
                Bucket=self.settings.cos_bucket,
                Key=object_key
            )
            
            return {
                "size": int(response.get('Content-Length', 0)),
                "content_type": response.get('Content-Type', ''),
                "last_modified": response.get('Last-Modified', ''),
                "etag": response.get('ETag', '').strip('"')
            }
        except Exception as e:
            logger.warning(f"获取对象信息失败: {object_key}, 错误: {e}")
            return None
    
    def generate_download_url(self, object_key: str, expires: int = 3600) -> str:
        """
        生成下载URL（用于后端下载文件）
        
        Args:
            object_key: 对象键名
            expires: 过期时间（秒）
            
        Returns:
            下载URL
        """
        try:
            download_url = self.client.get_presigned_url(
                Method='GET',
                Bucket=self.settings.cos_bucket,
                Key=object_key,
                Expired=expires
            )
            return download_url
        except Exception as e:
            logger.error(f"生成下载URL失败: {object_key}, 错误: {e}")
            raise RuntimeError(f"生成下载URL失败: {str(e)}")
    
    def delete_object(self, object_key: str) -> bool:
        """
        删除对象
        
        Args:
            object_key: 对象键名
            
        Returns:
            删除是否成功
        """
        try:
            self.client.delete_object(
                Bucket=self.settings.cos_bucket,
                Key=object_key
            )
            logger.info(f"删除对象成功: {object_key}")
            return True
        except Exception as e:
            logger.error(f"删除对象失败: {object_key}, 错误: {e}")
            return False


# 全局COS服务实例
_cos_service: Optional[COSService] = None


def get_cos_service() -> COSService:
    """获取COS服务实例（单例模式）"""
    global _cos_service
    if _cos_service is None:
        _cos_service = COSService()
    return _cos_service


def extract_object_key_from_url(public_url: str, cos_domain: str) -> Optional[str]:
    """
    从公开URL中提取对象键名
    
    Args:
        public_url: 公开访问URL
        cos_domain: COS域名
        
    Returns:
        对象键名或None
    """
    try:
        if cos_domain in public_url:
            # 提取域名后的路径部分
            parts = public_url.split(cos_domain)
            if len(parts) > 1:
                object_key = parts[1].lstrip('/')
                # URL解码
                from urllib.parse import unquote
                return unquote(object_key)
    except Exception as e:
        logger.warning(f"提取对象键名失败: {public_url}, 错误: {e}")
    
    return None
