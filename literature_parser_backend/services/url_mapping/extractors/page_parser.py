"""
页面解析器

提供通用的HTML页面解析功能。
"""

import re
import logging
import requests
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class PageParser:
    """HTML页面解析器"""
    
    # 默认请求头
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    @classmethod
    def fetch_page(cls, url: str, timeout: int = 10, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            timeout: 超时时间（秒）
            headers: 自定义请求头
            
        Returns:
            页面HTML内容，失败时返回None
        """
        try:
            request_headers = headers or cls.DEFAULT_HEADERS
            
            logger.debug(f"正在获取页面: {url}")
            response = requests.get(url, headers=request_headers, timeout=timeout)
            
            if response.status_code == 200:
                logger.debug(f"页面获取成功: {len(response.text)} 字符")
                return response.text
            else:
                logger.warning(f"页面访问失败，状态码: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"页面获取失败: {e}")
            return None
    
    @classmethod
    def extract_title(cls, content: str) -> Optional[str]:
        """
        从页面内容中提取标题
        
        Args:
            content: HTML页面内容
            
        Returns:
            页面标题，如果没有找到则返回None
        """
        # 尝试多种标题提取模式
        title_patterns = [
            r'<meta[^>]*name=["\']citation_title["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
            r'<title[^>]*>([^<]+)</title>',
            r'<h1[^>]*>([^<]+)</h1>',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # 清理标题
                title = re.sub(r'\s+', ' ', title)  # 合并多个空白字符
                title = title.replace('\n', ' ').replace('\r', ' ')
                if title and len(title) > 5:  # 基本有效性检查
                    logger.debug(f"提取到标题: {title[:50]}...")
                    return title
        
        return None
    
    @classmethod
    def extract_meta_content(cls, content: str, meta_name: str) -> Optional[str]:
        """
        从页面中提取指定meta标签的内容
        
        Args:
            content: HTML页面内容
            meta_name: meta标签的name或property值
            
        Returns:
            meta标签的content值，如果没有找到则返回None
        """
        patterns = [
            rf'<meta[^>]*name=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']+)["\']',
            rf'<meta[^>]*property=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']+)["\']',
            rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']?{re.escape(meta_name)}["\']?',
            rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']?{re.escape(meta_name)}["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                logger.debug(f"提取到meta {meta_name}: {value}")
                return value
        
        return None
    
    @classmethod
    def extract_links(cls, content: str, base_url: str, pattern: str) -> list:
        """
        从页面中提取匹配指定模式的链接
        
        Args:
            content: HTML页面内容
            base_url: 基础URL，用于解析相对链接
            pattern: 链接匹配的正则表达式模式
            
        Returns:
            匹配的链接列表
        """
        links = []
        
        # 查找所有href属性
        href_pattern = r'href=["\']([^"\']+)["\']'
        href_matches = re.findall(href_pattern, content, re.IGNORECASE)
        
        for href in href_matches:
            # 转换为绝对URL
            absolute_url = urljoin(base_url, href)
            
            # 检查是否匹配指定模式
            if re.search(pattern, absolute_url, re.IGNORECASE):
                links.append(absolute_url)
        
        logger.debug(f"找到 {len(links)} 个匹配链接")
        return links
    
    @classmethod
    def extract_json_ld(cls, content: str) -> list:
        """
        从页面中提取JSON-LD结构化数据
        
        Args:
            content: HTML页面内容
            
        Returns:
            JSON-LD数据列表
        """
        import json
        
        json_ld_data = []
        
        # 查找JSON-LD脚本标签
        pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                json_ld_data.append(data)
                logger.debug(f"提取到JSON-LD数据: {type(data)}")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON-LD解析失败: {e}")
        
        return json_ld_data
    
    @classmethod
    def is_valid_academic_page(cls, content: str) -> bool:
        """
        判断页面是否为学术论文页面
        
        Args:
            content: HTML页面内容
            
        Returns:
            是否为学术论文页面
        """
        # 检查学术论文页面的常见特征
        academic_indicators = [
            r'citation_title',
            r'citation_author',
            r'citation_doi',
            r'citation_journal',
            r'citation_conference',
            r'dc\.title',
            r'dc\.creator',
            r'prism\.doi',
        ]
        
        for indicator in academic_indicators:
            if re.search(indicator, content, re.IGNORECASE):
                return True
        
        return False
