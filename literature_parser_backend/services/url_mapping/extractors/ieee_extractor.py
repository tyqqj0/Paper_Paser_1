"""
IEEE专用提取器

专门处理IEEE Xplore网站的信息提取。
"""

import re
import logging
from typing import Optional, Dict, Any

from ..core.result import URLMappingResult
from .page_parser import PageParser
from .doi_extractor import DOIExtractor
from .meta_extractor import MetaExtractor

logger = logging.getLogger(__name__)


class IEEEExtractor:
    """IEEE专用信息提取器"""
    
    @classmethod
    def extract_document_id(cls, url: str) -> Optional[str]:
        """
        从IEEE URL中提取文档ID
        
        Args:
            url: IEEE URL
            
        Returns:
            文档ID，如果没有找到则返回None
        """
        doc_id_match = re.search(r"document/(\d+)", url)
        if doc_id_match:
            doc_id = doc_id_match.group(1)
            logger.debug(f"提取到IEEE文档ID: {doc_id}")
            return doc_id
        return None
    
    @classmethod
    def extract_from_page(cls, url: str) -> Optional[URLMappingResult]:
        """
        通过页面解析提取IEEE文献信息
        
        Args:
            url: IEEE页面URL
            
        Returns:
            提取结果，如果失败则返回None
        """
        try:
            # 提取文档ID
            doc_id = cls.extract_document_id(url)
            if not doc_id:
                logger.warning("无法从URL中提取IEEE文档ID")
                return None
            
            logger.info(f"尝试通过页面解析获取IEEE文档 {doc_id} 的信息")
            
            # 获取页面内容
            fetch_result = PageParser.fetch_page_with_details(url)
            if not fetch_result.success:
                logger.warning(f"无法获取IEEE页面内容: {fetch_result.error_message} (错误类型: {fetch_result.error_type})")
                return None
            
            content = fetch_result.content
            
            # 使用多种方法提取DOI
            doi = cls._extract_doi_from_content(content)
            if not doi:
                logger.warning("无法从IEEE页面提取DOI")
                return None
            
            # 创建结果
            result = URLMappingResult()
            result.doi = doi
            result.source_page_url = url
            result.venue = "IEEE"
            result.confidence = 0.95  # 高置信度，因为是从官方页面提取的
            
            # 尝试提取额外信息
            cls._extract_additional_info(content, result)
            
            logger.info(f"✅ 成功从IEEE页面提取信息: DOI={doi}")
            return result
            
        except Exception as e:
            logger.error(f"IEEE页面解析失败: {e}")
            return None
    
    @classmethod
    def _extract_doi_from_content(cls, content: str) -> Optional[str]:
        """
        从IEEE页面内容中提取DOI
        
        Args:
            content: 页面HTML内容
            
        Returns:
            提取到的DOI
        """
        # 方法1: 从meta标签提取
        doi = DOIExtractor.extract_from_content(content)
        if doi:
            logger.debug(f"从meta标签提取到DOI: {doi}")
            return doi
        
        # 方法2: IEEE特定的DOI模式
        ieee_doi_patterns = [
            # IEEE特定的DOI格式
            r'10\.1109/[A-Z0-9\.\-_]+\.\d{4}\.\d+',
            r'10\.23919/[A-Z0-9\.\-_]+\.\d{4}\.\d+',
            # 通用DOI模式（作为备选）
            r'10\.\d{4,}/[A-Za-z0-9\.\-_/]+',
        ]
        
        for pattern in ieee_doi_patterns:
            matches = re.findall(pattern, content)
            if matches:
                # 过滤掉明显不是DOI的结果
                valid_dois = [m for m in matches if cls._is_valid_ieee_doi(m)]
                if valid_dois:
                    doi = valid_dois[0]
                    logger.debug(f"从IEEE特定模式提取到DOI: {doi}")
                    return doi
        
        return None
    
    @classmethod
    def _is_valid_ieee_doi(cls, doi: str) -> bool:
        """
        验证是否为有效的IEEE DOI
        
        Args:
            doi: 要验证的DOI
            
        Returns:
            是否为有效的IEEE DOI
        """
        # 基本DOI验证
        if not DOIExtractor._is_valid_doi(doi):
            return False
        
        # IEEE特定验证
        ieee_prefixes = ['10.1109/', '10.23919/']
        if not any(doi.startswith(prefix) for prefix in ieee_prefixes):
            # 如果不是IEEE特定前缀，进行额外检查
            if len(doi) < 15:  # IEEE DOI通常较长
                return False
        
        return True
    
    @classmethod
    def _extract_additional_info(cls, content: str, result: URLMappingResult):
        """
        从IEEE页面提取额外信息
        
        Args:
            content: 页面HTML内容
            result: 要填充的结果对象
        """
        try:
            # 提取学术元数据
            metadata = MetaExtractor.extract_academic_metadata(content)
            
            # 填充结果对象
            if metadata.title:
                result.title = metadata.title
            
            if metadata.year:
                try:
                    result.year = int(metadata.year)
                except ValueError:
                    pass
            
            # 存储额外的元数据
            result.metadata.update({
                'authors': metadata.authors,
                'journal': metadata.journal,
                'conference': metadata.conference,
                'volume': metadata.volume,
                'issue': metadata.issue,
                'pages': metadata.pages,
                'abstract': metadata.abstract,
                'keywords': metadata.keywords,
                'publisher': metadata.publisher,
            })
            
            logger.debug(f"提取到额外信息: title={bool(metadata.title)}, authors={len(metadata.authors)}")
            
        except Exception as e:
            logger.warning(f"提取IEEE额外信息失败: {e}")
    
    @classmethod
    def extract_from_semantic_scholar(cls, url: str) -> Optional[URLMappingResult]:
        """
        通过Semantic Scholar查询IEEE文献信息
        
        Args:
            url: IEEE页面URL
            
        Returns:
            查询结果，如果失败则返回None
        """
        try:
            # 提取文档ID
            doc_id = cls.extract_document_id(url)
            if not doc_id:
                return None
            
            logger.info(f"尝试通过Semantic Scholar查询IEEE文档 {doc_id}")
            
            # 导入Semantic Scholar客户端
            from ....services.semantic_scholar import SemanticScholarClient
            
            client = SemanticScholarClient()
            
            # 构建查询字符串
            # 注意：这是一个实验性功能，可能需要根据实际API调整
            query = f"IEEE {doc_id}"
            
            # 这里需要实现具体的查询逻辑
            # 由于Semantic Scholar API的限制，这个功能可能需要进一步开发
            logger.debug("Semantic Scholar IEEE查询功能尚未完全实现")
            return None
            
        except Exception as e:
            logger.warning(f"Semantic Scholar IEEE查询失败: {e}")
            return None
    
    @classmethod
    def construct_doi_from_document_id(cls, doc_id: str) -> Optional[str]:
        """
        尝试从文档ID构建DOI（实验性功能）
        
        Args:
            doc_id: IEEE文档ID
            
        Returns:
            构建的DOI，如果无法构建则返回None
        """
        # 注意：这是一个实验性功能
        # IEEE的DOI格式通常不能直接从文档ID推导出来
        # 这里只是一个占位符实现
        
        logger.debug(f"尝试从文档ID构建DOI: {doc_id}")
        
        # 一些IEEE DOI的常见模式
        # 但这种方法不可靠，仅作为最后的备选方案
        possible_patterns = [
            f"10.1109/ACCESS.2022.{doc_id}",
            f"10.1109/TPAMI.2022.{doc_id}",
            f"10.23919/APMC55665.2022.{doc_id}",
        ]
        
        # 这里应该有更智能的逻辑来选择正确的模式
        # 但由于缺乏足够的信息，我们暂时返回None
        logger.debug("DOI构建功能需要更多信息，暂时返回None")
        return None
