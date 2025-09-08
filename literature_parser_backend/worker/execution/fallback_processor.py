"""
备选文献处理器

用于处理智能路由无法处理的情况，如纯DOI、ArXiv ID等标识符。
该处理器将创建基础的文献数据结构，然后通过DataPipeline进行统一处理和去重。
"""

import logging
from typing import Dict, Any, Optional
from ...models.literature import MetadataModel, IdentifiersModel
from ...utils.external_api.crossref_client import CrossRefClient
from ...utils.external_api.arxiv_client import ArxivClient

logger = logging.getLogger(__name__)


class FallbackProcessor:
    """备选文献处理器 - 处理智能路由无法处理的情况"""
    
    def __init__(self):
        self.crossref_client = CrossRefClient()
        self.arxiv_client = ArxivClient()
    
    async def process(self, source_data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        处理非智能路由情况的文献数据
        
        Args:
            source_data: 源数据（包含DOI、ArXiv ID等标识符）
            task_id: 任务ID
            
        Returns:
            处理结果字典，包含标识符、元数据等信息
        """
        logger.info(f"🔄 [备选处理器] Task {task_id}: 开始处理源数据")
        
        try:
            # 1. 从源数据中提取标识符
            identifiers = await self._extract_identifiers(source_data, task_id)
            
            # 2. 尝试获取元数据
            metadata = await self._fetch_metadata(identifiers, task_id)
            
            # 3. 构建处理结果
            result = {
                'success': True,
                'identifiers': identifiers,
                'metadata': metadata,
                'source_data': source_data,
                'processor_type': 'fallback'
            }
            
            logger.info(f"✅ [备选处理器] Task {task_id}: 处理完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ [备选处理器] Task {task_id}: 处理失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'fallback_processing_failed',
                'source_data': source_data
            }
    
    async def _extract_identifiers(self, source_data: Dict[str, Any], task_id: str) -> IdentifiersModel:
        """从源数据中提取标识符"""
        identifiers = IdentifiersModel()
        
        # 从source_data中提取DOI
        if 'doi' in source_data:
            identifiers.doi = source_data['doi']
            logger.info(f"🔗 [备选处理器] Task {task_id}: 提取DOI: {identifiers.doi}")
        
        # 从source_data中提取ArXiv ID
        if 'arxiv_id' in source_data:
            identifiers.arxiv_id = source_data['arxiv_id']
            logger.info(f"🔗 [备选处理器] Task {task_id}: 提取ArXiv ID: {identifiers.arxiv_id}")
        
        # 从URL中尝试提取标识符
        if 'url' in source_data:
            url = source_data['url']
            # 尝试从URL中提取DOI
            if 'doi.org' in url and not identifiers.doi:
                # 提取doi.org/后面的部分
                import re
                doi_match = re.search(r'doi\.org/(.+)', url)
                if doi_match:
                    identifiers.doi = doi_match.group(1)
                    logger.info(f"🔗 [备选处理器] Task {task_id}: 从URL提取DOI: {identifiers.doi}")
            
            # 尝试从URL中提取ArXiv ID
            if 'arxiv.org' in url and not identifiers.arxiv_id:
                arxiv_match = re.search(r'arxiv\.org/(?:abs/|pdf/)?(\d{4}\.\d{4,5})', url)
                if arxiv_match:
                    identifiers.arxiv_id = arxiv_match.group(1)
                    logger.info(f"🔗 [备选处理器] Task {task_id}: 从URL提取ArXiv ID: {identifiers.arxiv_id}")
        
        return identifiers
    
    async def _fetch_metadata(self, identifiers: IdentifiersModel, task_id: str) -> Optional[MetadataModel]:
        """根据标识符获取元数据"""
        metadata = None
        
        # 1. 优先使用DOI获取元数据
        if identifiers.doi:
            try:
                logger.info(f"📚 [备选处理器] Task {task_id}: 使用CrossRef获取DOI元数据: {identifiers.doi}")
                crossref_data = await self.crossref_client.get_work_by_doi(identifiers.doi)
                if crossref_data:
                    metadata = self._convert_crossref_to_metadata(crossref_data, task_id)
                    logger.info(f"✅ [备选处理器] Task {task_id}: CrossRef元数据获取成功")
            except Exception as e:
                logger.warning(f"⚠️ [备选处理器] Task {task_id}: CrossRef获取失败: {e}")
        
        # 2. 如果DOI失败，尝试使用ArXiv ID获取元数据
        if not metadata and identifiers.arxiv_id:
            try:
                logger.info(f"📚 [备选处理器] Task {task_id}: 使用ArXiv获取元数据: {identifiers.arxiv_id}")
                arxiv_data = await self.arxiv_client.get_paper_by_id(identifiers.arxiv_id)
                if arxiv_data:
                    metadata = self._convert_arxiv_to_metadata(arxiv_data, task_id)
                    logger.info(f"✅ [备选处理器] Task {task_id}: ArXiv元数据获取成功")
            except Exception as e:
                logger.warning(f"⚠️ [备选处理器] Task {task_id}: ArXiv获取失败: {e}")
        
        # 3. 如果都失败了，创建基础元数据
        if not metadata:
            logger.warning(f"⚠️ [备选处理器] Task {task_id}: 无法获取元数据，创建基础元数据")
            metadata = MetadataModel()
            # 使用标识符作为标题的备选方案
            if identifiers.doi:
                metadata.title = f"Literature with DOI: {identifiers.doi}"
            elif identifiers.arxiv_id:
                metadata.title = f"Literature with ArXiv ID: {identifiers.arxiv_id}"
            else:
                metadata.title = "Unknown Literature"
        
        return metadata
    
    def _convert_crossref_to_metadata(self, crossref_data: Dict[str, Any], task_id: str) -> MetadataModel:
        """将CrossRef数据转换为MetadataModel"""
        metadata = MetadataModel()
        
        # 基础信息
        if 'title' in crossref_data and crossref_data['title']:
            metadata.title = crossref_data['title'][0] if isinstance(crossref_data['title'], list) else crossref_data['title']
        
        if 'author' in crossref_data:
            authors = []
            for author in crossref_data['author']:
                given = author.get('given', '')
                family = author.get('family', '')
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)
            metadata.authors = authors
        
        # 发表信息
        if 'published-print' in crossref_data:
            date_parts = crossref_data['published-print'].get('date-parts')
            if date_parts and date_parts[0]:
                metadata.year = str(date_parts[0][0])
        elif 'published-online' in crossref_data:
            date_parts = crossref_data['published-online'].get('date-parts')
            if date_parts and date_parts[0]:
                metadata.year = str(date_parts[0][0])
        
        if 'container-title' in crossref_data and crossref_data['container-title']:
            metadata.journal = crossref_data['container-title'][0] if isinstance(crossref_data['container-title'], list) else crossref_data['container-title']
        
        logger.info(f"📚 [备选处理器] Task {task_id}: CrossRef转换完成 - 标题: {metadata.title}")
        return metadata
    
    def _convert_arxiv_to_metadata(self, arxiv_data: Dict[str, Any], task_id: str) -> MetadataModel:
        """将ArXiv数据转换为MetadataModel"""
        metadata = MetadataModel()
        
        # 基础信息
        if 'title' in arxiv_data:
            metadata.title = arxiv_data['title']
        
        if 'authors' in arxiv_data:
            metadata.authors = arxiv_data['authors']
        
        if 'published' in arxiv_data:
            # ArXiv日期格式通常是YYYY-MM-DD
            try:
                metadata.year = str(arxiv_data['published'][:4])
            except:
                pass
        
        if 'summary' in arxiv_data:
            metadata.abstract = arxiv_data['summary']
        
        # ArXiv特有信息
        metadata.journal = "arXiv preprint"
        
        logger.info(f"📚 [备选处理器] Task {task_id}: ArXiv转换完成 - 标题: {metadata.title}")
        return metadata



