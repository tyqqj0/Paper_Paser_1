"""
安全验证服务

提供文件上传和处理过程中的安全检查功能。
"""

import hashlib
import mimetypes
import os
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from loguru import logger


class SecurityValidator:
    """安全验证器"""
    
    # 危险文件扩展名黑名单
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
        '.sh', '.php', '.asp', '.aspx', '.jsp', '.py', '.pl', '.rb', '.ps1'
    }
    
    # 允许的PDF MIME类型
    ALLOWED_PDF_MIMES = {
        'application/pdf',
        'application/octet-stream'  # 有时PDF会被识别为这个
    }
    
    # 文件名中的危险字符
    DANGEROUS_FILENAME_CHARS = ['<', '>', ':', '"', '|', '?', '*', '\\', '/', '\0']
    
    # 危险的文件名模式
    DANGEROUS_FILENAME_PATTERNS = [
        r'^\.',  # 隐藏文件
        r'^\s*$',  # 空白文件名
        r'.*\.(exe|bat|cmd|com|pif|scr|vbs|js|jar|sh|php|asp|aspx|jsp|py|pl|rb|ps1)\.pdf$',  # 双扩展名
        r'.*\.(exe|bat|cmd|com|pif|scr|vbs|js|jar|sh|php|asp|aspx|jsp|py|pl|rb|ps1)$',  # 危险扩展名
        r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',  # Windows保留名称
        r'.*\.\.',  # 路径遍历
        r'.*/.*',  # 路径分隔符
        r'.*\\.*',  # Windows路径分隔符
    ]
    
    def __init__(self, max_file_size: int = 50 * 1024 * 1024):
        """
        初始化安全验证器
        
        Args:
            max_file_size: 最大文件大小（字节）
        """
        self.max_file_size = max_file_size
    
    def validate_filename(self, filename: str) -> Tuple[bool, str]:
        """
        验证文件名安全性
        
        Args:
            filename: 文件名
            
        Returns:
            (是否安全, 错误信息)
        """
        if not filename:
            return False, "文件名不能为空"
        
        # 检查文件名长度
        if len(filename) > 255:
            return False, "文件名过长（超过255字符）"
        
        # 检查危险字符
        for char in self.DANGEROUS_FILENAME_CHARS:
            if char in filename:
                return False, f"文件名包含危险字符: {char}"
        
        # 检查危险模式
        for pattern in self.DANGEROUS_FILENAME_PATTERNS:
            if re.match(pattern, filename, re.IGNORECASE):
                return False, f"文件名包含危险模式"

        # 额外检查：双扩展名
        if filename.lower().count('.') > 1:
            parts = filename.lower().split('.')
            if len(parts) >= 3:  # 至少有两个扩展名
                second_ext = parts[-2]
                if second_ext in ['exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jar', 'sh', 'php', 'asp', 'aspx', 'jsp', 'py', 'pl', 'rb', 'ps1']:
                    return False, f"检测到危险的双扩展名: .{second_ext}.pdf"
        
        # 检查文件扩展名
        _, ext = os.path.splitext(filename.lower())
        if ext in self.DANGEROUS_EXTENSIONS:
            return False, f"危险的文件扩展名: {ext}"
        
        # 检查是否为PDF文件
        if ext != '.pdf':
            return False, f"只允许PDF文件，当前扩展名: {ext}"
        
        return True, ""
    
    def validate_file_size(self, file_size: int) -> Tuple[bool, str]:
        """
        验证文件大小
        
        Args:
            file_size: 文件大小（字节）
            
        Returns:
            (是否合法, 错误信息)
        """
        if file_size <= 0:
            return False, "文件大小必须大于0"
        
        if file_size > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            return False, f"文件大小超过限制: {actual_mb:.1f}MB > {max_mb:.1f}MB"
        
        return True, ""
    
    def validate_mime_type(self, mime_type: str, filename: str) -> Tuple[bool, str]:
        """
        验证MIME类型
        
        Args:
            mime_type: MIME类型
            filename: 文件名
            
        Returns:
            (是否合法, 错误信息)
        """
        if mime_type not in self.ALLOWED_PDF_MIMES:
            return False, f"不支持的MIME类型: {mime_type}"
        
        # 检查MIME类型与文件扩展名是否匹配
        expected_mime = mimetypes.guess_type(filename)[0]
        if expected_mime and mime_type != expected_mime and mime_type != 'application/octet-stream':
            logger.warning(f"MIME类型不匹配: 期望 {expected_mime}, 实际 {mime_type}")
        
        return True, ""
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        验证URL安全性
        
        Args:
            url: URL地址
            
        Returns:
            (是否安全, 错误信息)
        """
        try:
            parsed = urlparse(url)
            
            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                return False, f"不支持的协议: {parsed.scheme}"
            
            # 检查主机名
            if not parsed.netloc:
                return False, "URL缺少主机名"
            
            # 检查是否为本地地址（防止SSRF攻击）
            hostname = parsed.hostname
            if hostname:
                # 检查是否为私有IP地址
                if self._is_private_ip(hostname):
                    return False, f"不允许访问私有IP地址: {hostname}"
                
                # 检查是否为本地地址
                if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                    return False, f"不允许访问本地地址: {hostname}"
            
            return True, ""
            
        except Exception as e:
            return False, f"URL格式错误: {str(e)}"
    
    def _is_private_ip(self, hostname: str) -> bool:
        """
        检查是否为私有IP地址
        
        Args:
            hostname: 主机名或IP地址
            
        Returns:
            是否为私有IP
        """
        try:
            import ipaddress
            ip = ipaddress.ip_address(hostname)
            return ip.is_private
        except ValueError:
            # 不是IP地址，可能是域名
            return False
    
    def validate_pdf_content(self, content: bytes) -> Tuple[bool, str]:
        """
        验证PDF内容
        
        Args:
            content: PDF文件内容
            
        Returns:
            (是否为有效PDF, 错误信息)
        """
        if not content:
            return False, "文件内容为空"
        
        # 检查PDF魔数
        if not content.startswith(b'%PDF-'):
            return False, "文件不是有效的PDF格式"
        
        # 检查文件大小
        if len(content) > self.max_file_size:
            max_mb = self.max_file_size / (1024 * 1024)
            actual_mb = len(content) / (1024 * 1024)
            return False, f"文件大小超过限制: {actual_mb:.1f}MB > {max_mb:.1f}MB"
        
        # 基本的PDF结构检查
        try:
            # 检查是否包含PDF结束标记
            if b'%%EOF' not in content[-1024:]:  # 在最后1KB中查找
                logger.warning("PDF文件可能不完整（缺少EOF标记）")
            
            # 检查是否包含基本的PDF对象
            if b'obj' not in content or b'endobj' not in content:
                return False, "PDF文件结构异常（缺少对象定义）"
            
        except Exception as e:
            logger.warning(f"PDF结构检查失败: {e}")
        
        return True, ""
    
    def generate_file_hash(self, content: bytes) -> str:
        """
        生成文件内容的哈希值
        
        Args:
            content: 文件内容
            
        Returns:
            SHA256哈希值
        """
        return hashlib.sha256(content).hexdigest()
    
    def validate_upload_request(
        self, 
        filename: str, 
        mime_type: str, 
        file_size: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        综合验证上传请求
        
        Args:
            filename: 文件名
            mime_type: MIME类型
            file_size: 文件大小（可选）
            
        Returns:
            (是否通过验证, 错误信息列表)
        """
        errors = []
        
        # 验证文件名
        is_valid, error = self.validate_filename(filename)
        if not is_valid:
            errors.append(f"文件名验证失败: {error}")
        
        # 验证MIME类型
        is_valid, error = self.validate_mime_type(mime_type, filename)
        if not is_valid:
            errors.append(f"MIME类型验证失败: {error}")
        
        # 验证文件大小（如果提供）
        if file_size is not None:
            is_valid, error = self.validate_file_size(file_size)
            if not is_valid:
                errors.append(f"文件大小验证失败: {error}")
        
        return len(errors) == 0, errors


# 全局安全验证器实例
_security_validator: Optional[SecurityValidator] = None


def get_security_validator(max_file_size: Optional[int] = None) -> SecurityValidator:
    """获取安全验证器实例（单例模式）"""
    global _security_validator
    if _security_validator is None:
        from ..settings import Settings
        settings = Settings()
        _security_validator = SecurityValidator(
            max_file_size=max_file_size or settings.upload_max_file_size
        )
    return _security_validator
