#!/usr/bin/env python3
"""
GROBID元数据处理器 - Paper Parser 0.2

使用GROBID服务从PDF文件中提取元数据，作为其他API处理器的回退方案。
主要处理直接PDF文件或无法通过其他API获取元数据的情况。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import tempfile
import os

from ....models.literature import AuthorModel, MetadataModel
from ....services.grobid import GrobidClient
from ....services.request_manager import ExternalRequestManager, RequestType
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class GrobidProcessor(MetadataProcessor):
    """
    GROBID元数据处理器。
    
    使用GROBID服务从PDF文件中直接提取元数据，主要作为其他API处理器的回退方案。
    优先级：30（PDF处理器，较低优先级）
    
    特点：
    - 直接从PDF文件提取元数据
    - 处理无法通过其他API获取的文献
    - 提供基础的作者、标题、摘要等信息
    - 作为最后的回退选项
    """
    
    def __init__(self, settings=None):
        """初始化GROBID处理器"""
        super().__init__(settings)
        self.grobid_client = GrobidClient(settings)
        self.request_manager = ExternalRequestManager(settings)
    
    @property
    def name(self) -> str:
        """处理器名称"""
        return "GROBID"
    
    @property
    def processor_type(self) -> ProcessorType:
        """处理器类型"""
        return ProcessorType.PDF_PARSER
    
    @property
    def priority(self) -> int:
        """处理器优先级（PDF处理器，较低优先级）"""
        return 30
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        检查是否可以处理给定的标识符。
        
        GROBID处理器可以处理：
        1. 直接的PDF文件路径
        2. PDF URL
        3. 作为其他处理器的回退选项
        
        Args:
            identifiers: 包含各种标识符的数据对象
            
        Returns:
            bool: 如果可以处理则返回True
        """
        # 检查是否有PDF文件路径
        if identifiers.file_path and identifiers.file_path.lower().endswith('.pdf'):
            return True
            
        # 检查是否有PDF URL
        if identifiers.url and identifiers.url.lower().endswith('.pdf'):
            return True
            
        # 作为回退选项，如果有标题但没有其他强标识符
        if identifiers.title and not any([
            identifiers.doi,
            identifiers.arxiv_id,
            identifiers.pmid,
            identifiers.semantic_scholar_id
        ]):
            return True
            
        return False
    
    async def process(
        self,
        identifiers: IdentifierData,
        existing_metadata: Optional[MetadataModel] = None
    ) -> ProcessorResult:
        """
        处理元数据提取。
        
        Args:
            identifiers: 包含各种标识符的数据对象
            existing_metadata: 现有的元数据（可选）
            
        Returns:
            ProcessorResult: 处理结果
        """
        try:
            logger.info(f"开始GROBID元数据处理: {identifiers}")
            
            # 准备PDF文件
            pdf_path = await self._prepare_pdf_file(identifiers)
            if not pdf_path:
                return ProcessorResult(
                    success=False,
                    metadata=None,
                    error="无法获取PDF文件",
                    source=self.name
                )
            
            # 使用GROBID提取元数据
            metadata = await self._extract_metadata_from_pdf(pdf_path)
            
            if metadata:
                logger.info(f"GROBID成功提取元数据: {metadata.title}")
                return ProcessorResult(
                    success=True,
                    metadata=metadata,
                    error=None,
                    source=self.name
                )
            else:
                return ProcessorResult(
                    success=False,
                    metadata=None,
                    error="GROBID未能提取到有效元数据",
                    source=self.name
                )
                
        except Exception as e:
            logger.error(f"GROBID处理器错误: {str(e)}")
            return ProcessorResult(
                success=False,
                metadata=None,
                error=f"GROBID处理错误: {str(e)}",
                source=self.name
            )
    
    async def _prepare_pdf_file(self, identifiers: IdentifierData) -> Optional[str]:
        """
        准备PDF文件用于处理。
        
        Args:
            identifiers: 标识符数据
            
        Returns:
            Optional[str]: PDF文件路径，如果失败则返回None
        """
        # 如果已经有本地文件路径
        if identifiers.file_path and os.path.exists(identifiers.file_path):
            if identifiers.file_path.lower().endswith('.pdf'):
                return identifiers.file_path
        
        # 如果有PDF URL，下载文件
        if identifiers.url and identifiers.url.lower().endswith('.pdf'):
            try:
                # 使用download_file方法下载PDF
                pdf_content = self.request_manager.download_file(
                    url=identifiers.url,
                    request_type=RequestType.EXTERNAL
                )
                
                if pdf_content:
                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                        temp_file.write(pdf_content)
                        return temp_file.name
                        
            except Exception as e:
                logger.error(f"下载PDF文件失败: {str(e)}")
        
        return None
    
    async def _extract_metadata_from_pdf(self, pdf_path: str) -> Optional[MetadataModel]:
        """
        使用GROBID从PDF文件提取元数据。
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Optional[MetadataModel]: 提取的元数据，如果失败则返回None
        """
        try:
            # 读取PDF文件内容
            with open(pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # 使用GROBID客户端处理PDF
            grobid_result = self.grobid_client.process_pdf(pdf_content)
            
            if not grobid_result or grobid_result.get('status') != 'success':
                return None
            
            # 解析GROBID结果
            metadata = self._parse_grobid_result(grobid_result)
            
            # 清理临时文件（如果是临时文件）
            if pdf_path.startswith(tempfile.gettempdir()):
                try:
                    os.unlink(pdf_path)
                except:
                    pass
            
            return metadata
            
        except Exception as e:
            logger.error(f"GROBID元数据提取失败: {str(e)}")
            return None
    
    def _parse_grobid_result(self, grobid_result: Dict[str, Any]) -> Optional[MetadataModel]:
        """
        解析GROBID返回的结果。
        
        Args:
            grobid_result: GROBID处理结果
            
        Returns:
            Optional[MetadataModel]: 解析后的元数据
        """
        try:
            # 从GROBID结果中提取metadata部分
            metadata_dict = grobid_result.get('metadata', {})
            if not metadata_dict:
                logger.warning("GROBID结果中没有metadata字段")
                return None
                
            # 提取基本信息
            title = metadata_dict.get('title', '').strip()
            if not title:
                logger.warning("GROBID结果中没有title")
                return None
            
            # 提取作者信息
            authors = []
            author_data = metadata_dict.get('authors', [])
            for author_info in author_data:
                if isinstance(author_info, dict):
                    name = author_info.get('full_name', '').strip()
                    if name:
                        authors.append(AuthorModel(
                            name=name,
                            affiliation=None  # GROBID返回格式中没有详细的affiliation
                        ))
            
            # 提取其他信息
            abstract = metadata_dict.get('abstract', '').strip() or None
            publication_date = metadata_dict.get('year', '').strip() or None
            journal = metadata_dict.get('journal', '').strip() or None
            publisher = metadata_dict.get('publisher', '').strip() or None
            
            # 创建元数据对象
            metadata = MetadataModel(
                title=title,
                authors=authors,
                abstract=abstract,
                publication_date=publication_date,
                journal=journal,
                publisher=publisher,
                source_priority=[self.name]
            )
            
            return metadata
            
        except Exception as e:
            logger.error(f"解析GROBID结果失败: {str(e)}")
            return None
    
    def validate_metadata(self, metadata: MetadataModel) -> bool:
        """
        验证元数据的完整性。
        
        Args:
            metadata: 要验证的元数据
            
        Returns:
            bool: 如果元数据有效则返回True
        """
        # GROBID的基本验证：至少需要标题
        if not metadata.title or len(metadata.title.strip()) < 10:
            return False
        
        # 检查是否有基本的作者信息
        if not metadata.authors or len(metadata.authors) == 0:
            logger.warning("GROBID提取的元数据缺少作者信息")
        
        return True


# 自动注册处理器
from ..registry import register_processor
register_processor(GrobidProcessor)
