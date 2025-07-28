"""
Meta标签提取器

专门用于从HTML页面中提取学术论文相关的meta标签信息。
"""

import re
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AcademicMetadata:
    """学术论文元数据"""
    title: Optional[str] = None
    authors: List[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    conference: Optional[str] = None
    year: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = None
    publisher: Optional[str] = None
    
    def __post_init__(self):
        if self.authors is None:
            self.authors = []
        if self.keywords is None:
            self.keywords = []


class MetaExtractor:
    """Meta标签提取器"""
    
    # 学术论文相关的meta标签映射
    META_MAPPINGS = {
        # 标题
        'title': [
            'citation_title',
            'dc.title',
            'prism.title',
            'og:title',
        ],
        
        # 作者
        'authors': [
            'citation_author',
            'dc.creator',
            'dc.contributor',
        ],
        
        # DOI
        'doi': [
            'citation_doi',
            'dc.identifier',
            'prism.doi',
            'doi',
        ],
        
        # 期刊
        'journal': [
            'citation_journal_title',
            'citation_journal',
            'dc.source',
            'prism.publicationName',
        ],
        
        # 会议
        'conference': [
            'citation_conference_title',
            'citation_conference',
        ],
        
        # 年份
        'year': [
            'citation_publication_date',
            'citation_date',
            'dc.date',
            'prism.publicationDate',
        ],
        
        # 卷号
        'volume': [
            'citation_volume',
            'prism.volume',
        ],
        
        # 期号
        'issue': [
            'citation_issue',
            'prism.number',
        ],
        
        # 页码
        'pages': [
            'citation_firstpage',
            'citation_lastpage',
            'prism.startingPage',
            'prism.endingPage',
        ],
        
        # 摘要
        'abstract': [
            'citation_abstract',
            'dc.description',
            'description',
        ],
        
        # 关键词
        'keywords': [
            'citation_keywords',
            'dc.subject',
            'keywords',
        ],
        
        # 出版商
        'publisher': [
            'citation_publisher',
            'dc.publisher',
        ],
    }
    
    @classmethod
    def extract_academic_metadata(cls, content: str) -> AcademicMetadata:
        """
        从HTML内容中提取学术论文元数据
        
        Args:
            content: HTML页面内容
            
        Returns:
            提取到的学术元数据
        """
        metadata = AcademicMetadata()
        
        # 提取单值字段
        for field, meta_names in cls.META_MAPPINGS.items():
            if field in ['authors', 'keywords']:
                continue  # 多值字段单独处理
            
            value = cls._extract_single_meta_value(content, meta_names)
            if value:
                setattr(metadata, field, value)
        
        # 提取作者信息（多值）
        metadata.authors = cls._extract_authors(content)
        
        # 提取关键词（多值）
        metadata.keywords = cls._extract_keywords(content)
        
        # 后处理
        cls._post_process_metadata(metadata)
        
        logger.debug(f"提取到学术元数据: title={metadata.title}, authors={len(metadata.authors)}, doi={metadata.doi}")
        return metadata
    
    @classmethod
    def _extract_single_meta_value(cls, content: str, meta_names: List[str]) -> Optional[str]:
        """
        提取单个meta标签值
        
        Args:
            content: HTML内容
            meta_names: 要查找的meta标签名称列表
            
        Returns:
            找到的第一个有效值
        """
        for meta_name in meta_names:
            value = cls._extract_meta_content(content, meta_name)
            if value:
                return value
        return None
    
    @classmethod
    def _extract_meta_content(cls, content: str, meta_name: str) -> Optional[str]:
        """
        从页面中提取指定meta标签的内容
        
        Args:
            content: HTML页面内容
            meta_name: meta标签的name或property值
            
        Returns:
            meta标签的content值
        """
        patterns = [
            rf'<meta[^>]*name=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']*)["\']',
            rf'<meta[^>]*property=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']*)["\']',
            rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']?{re.escape(meta_name)}["\']?',
            rf'<meta[^>]*content=["\']([^"\']*)["\'][^>]*property=["\']?{re.escape(meta_name)}["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:  # 确保不是空字符串
                    return value
        
        return None
    
    @classmethod
    def _extract_authors(cls, content: str) -> List[str]:
        """
        提取作者信息
        
        Args:
            content: HTML页面内容
            
        Returns:
            作者姓名列表
        """
        authors = []
        
        # 查找所有作者相关的meta标签
        author_meta_names = cls.META_MAPPINGS['authors']
        
        for meta_name in author_meta_names:
            # 查找所有匹配的meta标签
            patterns = [
                rf'<meta[^>]*name=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']*)["\']',
                rf'<meta[^>]*property=["\']?{re.escape(meta_name)}["\']?[^>]*content=["\']([^"\']*)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    author = match.strip()
                    if author and author not in authors:
                        authors.append(author)
        
        return authors
    
    @classmethod
    def _extract_keywords(cls, content: str) -> List[str]:
        """
        提取关键词
        
        Args:
            content: HTML页面内容
            
        Returns:
            关键词列表
        """
        keywords = []
        
        keyword_meta_names = cls.META_MAPPINGS['keywords']
        
        for meta_name in keyword_meta_names:
            value = cls._extract_meta_content(content, meta_name)
            if value:
                # 关键词通常用逗号、分号或其他分隔符分隔
                separators = [',', ';', '|', '\n']
                keyword_list = [value]
                
                for sep in separators:
                    new_list = []
                    for item in keyword_list:
                        new_list.extend([k.strip() for k in item.split(sep)])
                    keyword_list = new_list
                
                # 过滤空值并去重
                for keyword in keyword_list:
                    if keyword and keyword not in keywords:
                        keywords.append(keyword)
        
        return keywords
    
    @classmethod
    def _post_process_metadata(cls, metadata: AcademicMetadata):
        """
        后处理元数据
        
        Args:
            metadata: 要处理的元数据对象
        """
        # 清理DOI
        if metadata.doi:
            # 移除DOI前缀
            if metadata.doi.startswith('doi:'):
                metadata.doi = metadata.doi[4:]
            # 移除URL前缀
            if metadata.doi.startswith('http://dx.doi.org/'):
                metadata.doi = metadata.doi[18:]
            elif metadata.doi.startswith('https://doi.org/'):
                metadata.doi = metadata.doi[16:]
            elif metadata.doi.startswith('http://doi.org/'):
                metadata.doi = metadata.doi[15:]
        
        # 提取年份
        if metadata.year:
            year_match = re.search(r'(\d{4})', metadata.year)
            if year_match:
                metadata.year = year_match.group(1)
        
        # 清理标题
        if metadata.title:
            # 移除多余的空白字符
            metadata.title = re.sub(r'\s+', ' ', metadata.title).strip()
            # 移除HTML实体
            metadata.title = metadata.title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    @classmethod
    def extract_citation_info(cls, content: str) -> Dict[str, str]:
        """
        提取引用信息的简化版本
        
        Args:
            content: HTML页面内容
            
        Returns:
            包含基本引用信息的字典
        """
        citation_info = {}
        
        # 基本字段映射
        basic_fields = {
            'title': ['citation_title', 'dc.title'],
            'doi': ['citation_doi', 'dc.identifier'],
            'journal': ['citation_journal_title', 'dc.source'],
            'year': ['citation_publication_date', 'dc.date'],
        }
        
        for field, meta_names in basic_fields.items():
            value = cls._extract_single_meta_value(content, meta_names)
            if value:
                citation_info[field] = value
        
        return citation_info
