"""
ArXiv Official API Client

提供对arXiv官方API的访问，用于获取arXiv论文的元数据
"""

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from loguru import logger

from literature_parser_backend.models.literature import AuthorModel, MetadataModel
from literature_parser_backend.services.request_manager import ExternalRequestManager, RequestType
from literature_parser_backend.settings import Settings


class ArXivAPIClient:
    """arXiv官方API客户端"""
    
    def __init__(self, settings: Optional[Settings] = None):
        """初始化arXiv API客户端"""
        self.settings = settings or Settings()
        self.request_manager = ExternalRequestManager(self.settings)
        self.base_url = "http://export.arxiv.org/api/query"
        self.timeout = 30
        
    def get_metadata(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        通过arXiv ID获取论文元数据
        
        Args:
            arxiv_id: arXiv ID (例如: "2301.00001")
            
        Returns:
            包含论文元数据的字典，如果失败则返回None
        """
        logger.info(f"Fetching metadata from arXiv API for ID: {arxiv_id}")
        
        try:
            # 构建API请求URL
            params = {
                "id_list": arxiv_id,
                "max_results": 1
            }
            
            response = self.request_manager.get(
                url=self.base_url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return self._parse_arxiv_response(response.text, arxiv_id)
            else:
                logger.warning(f"arXiv API returned status {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching from arXiv API: {e}")
            return None
    
    def search_by_title(self, title: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        通过标题搜索arXiv论文
        
        Args:
            title: 论文标题
            max_results: 最大返回结果数
            
        Returns:
            匹配的论文列表
        """
        logger.info(f"Searching arXiv by title: {title}")
        
        try:
            # 构建搜索查询
            # 使用title字段搜索，并清理标题中的特殊字符
            search_query = f'ti:"{title}"'
            
            params = {
                "search_query": search_query,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending"
            }
            
            response = self.request_manager.get(
                url=self.base_url,
                request_type=RequestType.EXTERNAL,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return self._parse_arxiv_search_response(response.text, title)
            else:
                logger.warning(f"arXiv search API returned status {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching arXiv by title: {e}")
            return []
    
    def _parse_arxiv_response(self, xml_content: str, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        解析arXiv API的XML响应
        
        Args:
            xml_content: XML响应内容
            arxiv_id: 请求的arXiv ID
            
        Returns:
            解析后的元数据字典
        """
        try:
            # 解析XML
            root = ET.fromstring(xml_content)
            
            # 定义命名空间
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            # 查找entry元素
            entries = root.findall('atom:entry', namespaces)
            
            if not entries:
                logger.warning(f"No entries found for arXiv ID: {arxiv_id}")
                return None
            
            entry = entries[0]  # 取第一个结果
            
            # 提取基本信息
            title_elem = entry.find('atom:title', namespaces)
            title = title_elem.text.strip() if title_elem is not None else "Unknown Title"
            
            # 清理标题（移除多余的空白字符）
            title = re.sub(r'\s+', ' ', title)
            
            # 提取摘要
            summary_elem = entry.find('atom:summary', namespaces)
            abstract = summary_elem.text.strip() if summary_elem is not None else None
            
            # 清理摘要
            if abstract:
                abstract = re.sub(r'\s+', ' ', abstract)
            
            # 提取作者
            authors = []
            author_elems = entry.findall('atom:author', namespaces)
            for author_elem in author_elems:
                name_elem = author_elem.find('atom:name', namespaces)
                if name_elem is not None:
                    author_name = name_elem.text.strip()
                    authors.append(author_name)
            
            # 提取发布日期
            published_elem = entry.find('atom:published', namespaces)
            published_date = None
            year = None
            if published_elem is not None:
                published_date = published_elem.text.strip()
                # 从日期中提取年份 (格式: 2023-01-01T00:00:00Z)
                year_match = re.match(r'(\d{4})', published_date)
                if year_match:
                    year = int(year_match.group(1))
            
            # 提取分类
            categories = []
            category_elems = entry.findall('atom:category', namespaces)
            for cat_elem in category_elems:
                term = cat_elem.get('term')
                if term:
                    categories.append(term)
            
            # 提取DOI（如果有）
            doi = None
            doi_elem = entry.find('arxiv:doi', namespaces)
            if doi_elem is not None:
                doi = doi_elem.text.strip()
            
            # 提取期刊信息（如果有）
            journal_ref = None
            journal_elem = entry.find('arxiv:journal_ref', namespaces)
            if journal_elem is not None:
                journal_ref = journal_elem.text.strip()
            
            # 构建结果字典
            result = {
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'year': year,
                'published_date': published_date,
                'categories': categories,
                'doi': doi,
                'journal_ref': journal_ref,
                'arxiv_id': arxiv_id,
                'source': 'arxiv_api'
            }
            
            logger.info(f"✅ Successfully parsed arXiv metadata for {arxiv_id}")
            logger.debug(f"Title: {title}")
            logger.debug(f"Authors: {len(authors)} authors")
            logger.debug(f"Year: {year}")
            
            return result
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error for arXiv response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing arXiv response: {e}")
            return None
    
    def _parse_arxiv_search_response(self, xml_content: str, search_title: str) -> List[Dict[str, Any]]:
        """
        解析arXiv搜索API的XML响应
        
        Args:
            xml_content: XML响应内容
            search_title: 搜索的标题（用于日志）
            
        Returns:
            解析后的论文列表
        """
        try:
            results = []
            # 解析XML
            root = ET.fromstring(xml_content)
            
            # 定义命名空间
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }
            
            # 查找所有entry元素
            entries = root.findall('atom:entry', namespaces)
            
            if not entries:
                logger.info(f"No arXiv results found for title: {search_title}")
                return []
            
            logger.info(f"Found {len(entries)} arXiv results for title search")
            
            for entry in entries:
                # 提取arXiv ID
                id_elem = entry.find('atom:id', namespaces)
                if id_elem is None:
                    continue
                    
                # 从URL中提取arXiv ID
                arxiv_url = id_elem.text.strip()
                arxiv_id = self.extract_arxiv_id_from_url(arxiv_url)
                if not arxiv_id:
                    continue
                
                # 使用现有的解析逻辑解析单个entry
                entry_xml = ET.tostring(entry, encoding='unicode')
                # 创建一个临时的根元素包装这个entry
                temp_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
{entry_xml}
</feed>'''
                
                paper_data = self._parse_arxiv_response(temp_xml, arxiv_id)
                if paper_data:
                    results.append(paper_data)
            
            logger.info(f"Successfully parsed {len(results)} arXiv papers from search")
            return results
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error for arXiv search response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing arXiv search response: {e}")
            return []
    
    def convert_to_metadata_model(self, arxiv_data: Dict[str, Any]) -> MetadataModel:
        """
        将arXiv API数据转换为MetadataModel
        
        Args:
            arxiv_data: arXiv API返回的数据字典
            
        Returns:
            MetadataModel实例
        """
        # 转换作者列表
        authors = []
        for author_name in arxiv_data.get('authors', []):
            if isinstance(author_name, str) and author_name.strip():
                authors.append(AuthorModel(name=author_name.strip()))
        
        # 构建期刊信息
        journal = None
        if arxiv_data.get('journal_ref'):
            journal = arxiv_data['journal_ref']
        elif arxiv_data.get('categories'):
            # 使用主要分类作为期刊信息
            primary_category = arxiv_data['categories'][0]
            journal = f"arXiv preprint ({primary_category})"
        
        metadata = MetadataModel(
            title=arxiv_data.get('title', 'Unknown Title'),
            authors=authors,
            year=arxiv_data.get('year'),
            journal=journal,
            abstract=arxiv_data.get('abstract'),
            keywords=arxiv_data.get('categories', [])  # 使用分类作为关键词
        )
        
        return metadata
    
    def extract_arxiv_id_from_url(self, url: str) -> Optional[str]:
        """
        从URL中提取arXiv ID
        
        Args:
            url: arXiv URL
            
        Returns:
            arXiv ID，如果无法提取则返回None
        """
        patterns = [
            r'arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?',
            r'arxiv\.org/(?:abs|pdf|html)/([a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def is_arxiv_url(self, url: str) -> bool:
        """
        检查URL是否为arXiv URL
        
        Args:
            url: 要检查的URL
            
        Returns:
            是否为arXiv URL
        """
        return 'arxiv.org' in url.lower()
    
    def validate_arxiv_id(self, arxiv_id: str) -> bool:
        """
        验证arXiv ID格式是否正确
        
        Args:
            arxiv_id: 要验证的arXiv ID
            
        Returns:
            ID格式是否正确
        """
        patterns = [
            r'^\d{4}\.\d{4,5}(v\d+)?$',  # 新格式: 2301.00001
            r'^[a-z-]+/\d{7}(v\d+)?$'   # 旧格式: math-ph/0001001
        ]
        
        return any(re.match(pattern, arxiv_id) for pattern in patterns)
