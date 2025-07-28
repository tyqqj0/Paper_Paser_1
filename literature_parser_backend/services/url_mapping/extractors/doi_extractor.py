"""
DOI提取器

提供通用的DOI提取功能，支持从URL和页面内容中提取DOI。
"""

import re
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class DOIExtractor:
    """DOI提取器类"""
    
    # 标准DOI正则表达式
    DOI_PATTERN = r'10\.\d{4,}/[A-Za-z0-9\.\-_/]+'
    
    # Meta标签中的DOI模式
    META_PATTERNS = [
        r'<meta[^>]*name=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]*property=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]*name=["\']DC\.identifier["\'][^>]*content=["\']doi:([^"\']+)["\']',
        r'<meta[^>]*name=["\']doi["\'][^>]*content=["\']([^"\']+)["\']',
    ]
    
    # DOI链接模式
    DOI_LINK_PATTERNS = [
        r'https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s"\'<>]+)',
        r'https?://doi\.org/(10\.\d{4,}/[^\s"\'<>]+)',
        r'doi\.org/(10\.\d{4,}/[^\s"\'<>]+)',
    ]
    
    @classmethod
    def extract_from_url(cls, url: str) -> Optional[str]:
        """
        从URL中直接提取DOI
        
        Args:
            url: 要解析的URL
            
        Returns:
            提取到的DOI，如果没有找到则返回None
        """
        match = re.search(cls.DOI_PATTERN, url)
        if match:
            doi = match.group()
            logger.debug(f"从URL提取到DOI: {doi}")
            return doi
        return None
    
    @classmethod
    def extract_from_content(cls, content: str) -> Optional[str]:
        """
        从页面内容中提取DOI
        
        Args:
            content: HTML页面内容
            
        Returns:
            提取到的DOI，如果没有找到则返回None
        """
        # 1. 尝试从meta标签提取
        for pattern in cls.META_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                doi = match.group(1)
                logger.debug(f"从meta标签提取到DOI: {doi}")
                return doi
        
        # 2. 尝试从DOI链接提取
        for pattern in cls.DOI_LINK_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                doi = match.group(1)
                logger.debug(f"从DOI链接提取到DOI: {doi}")
                return doi
        
        # 3. 尝试从页面内容直接匹配
        matches = re.findall(cls.DOI_PATTERN, content)
        if matches:
            # 过滤掉明显不是DOI的结果
            valid_dois = [m for m in matches if cls._is_valid_doi(m)]
            if valid_dois:
                doi = valid_dois[0]  # 取第一个有效的DOI
                logger.debug(f"从页面内容提取到DOI: {doi}")
                return doi
        
        return None
    
    @classmethod
    def extract_all_from_content(cls, content: str) -> List[str]:
        """
        从页面内容中提取所有可能的DOI
        
        Args:
            content: HTML页面内容
            
        Returns:
            所有找到的DOI列表
        """
        dois = []
        
        # 1. 从meta标签提取
        for pattern in cls.META_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            dois.extend(matches)
        
        # 2. 从DOI链接提取
        for pattern in cls.DOI_LINK_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            dois.extend(matches)
        
        # 3. 从页面内容直接匹配
        content_matches = re.findall(cls.DOI_PATTERN, content)
        valid_content_dois = [m for m in content_matches if cls._is_valid_doi(m)]
        dois.extend(valid_content_dois)
        
        # 去重并返回
        unique_dois = list(dict.fromkeys(dois))  # 保持顺序的去重
        logger.debug(f"从页面内容提取到 {len(unique_dois)} 个DOI: {unique_dois}")
        return unique_dois
    
    @classmethod
    def _is_valid_doi(cls, doi: str) -> bool:
        """
        验证DOI是否有效
        
        Args:
            doi: 要验证的DOI
            
        Returns:
            是否为有效DOI
        """
        # 基本长度检查
        if len(doi) < 10:
            return False
        
        # 必须包含斜杠
        if '/' not in doi:
            return False
        
        # 不应该包含明显的非DOI内容
        invalid_patterns = [
            r'IEEE',  # IEEE不应该出现在DOI中
            r'\.pdf$',  # 不应该以.pdf结尾
            r'\.html$',  # 不应该以.html结尾
            r'\s',  # 不应该包含空格
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, doi, re.IGNORECASE):
                return False
        
        return True
