#!/usr/bin/env python3
"""
CrossRef元数据处理器 - Paper Parser 0.2

整合现有的CrossRef客户端和直接API调用，使用统一的标题匹配工具简化过滤逻辑。
支持DOI查询和标题搜索两种模式。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from ....models.literature import AuthorModel, MetadataModel
from ....services.crossref import CrossRefClient
from ....services.request_manager import ExternalRequestManager, RequestType
from ....utils.title_matching import TitleMatchingUtils
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class CrossRefProcessor(MetadataProcessor):
    """
    CrossRef元数据处理器。
    
    整合现有的DOI查询和标题搜索功能，使用简化的过滤逻辑。
    优先级：5（主要API服务之一）
    """
    
    def __init__(self, settings=None):
        """初始化CrossRef处理器"""
        super().__init__(settings)
        self.crossref_client = CrossRefClient(settings)
        self.request_manager = ExternalRequestManager(settings)
    
    @property
    def name(self) -> str:
        """处理器名称"""
        return "CrossRef"
    
    @property
    def processor_type(self) -> ProcessorType:
        """处理器类型"""
        return ProcessorType.API
    
    @property
    def priority(self) -> int:
        """处理器优先级（较高优先级）"""
        return 5
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        检查是否可以处理给定的标识符。
        
        支持：DOI直接查询，或有标题的情况下进行搜索。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            True if 可以处理这些标识符
        """
        # 如果有DOI，直接可以处理
        if identifiers.doi:
            return True
            
        # 如果有标题，可以进行搜索
        if identifiers.title and len(identifiers.title.strip()) > 10:
            return True
            
        return False
    
    async def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        处理标识符并返回元数据。
        
        逻辑：
        1. 优先DOI查询（准确性最高）
        2. 标题搜索 + 简化过滤（使用统一标题匹配工具）
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            ProcessorResult with 成功状态和元数据
        """
        try:
            # 1. 优先DOI查询
            if identifiers.doi:
                logger.info(f"🔍 CrossRef DOI查询: {identifiers.doi}")
                result = await self._process_by_doi(identifiers.doi)
                if result.success:
                    return result
                logger.info("DOI查询失败，尝试标题搜索...")
            
            # 2. 标题搜索（如果有标题）
            if identifiers.title:
                logger.info(f"🔍 CrossRef标题搜索: '{identifiers.title[:50]}...'")
                result = await self._process_by_title(identifiers.title, identifiers.year)
                if result.success:
                    return result
            
            # 3. 无法处理
            return ProcessorResult(
                success=False,
                error="CrossRef: No DOI or valid title provided",
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"CrossRef处理器异常: {e}")
            return ProcessorResult(
                success=False,
                error=f"CrossRef处理器异常: {str(e)}",
                source=self.name
            )
    
    async def _process_by_doi(self, doi: str) -> ProcessorResult:
        """
        通过DOI查询CrossRef元数据。
        
        Args:
            doi: DOI标识符
            
        Returns:
            ProcessorResult with 查询结果
        """
        try:
            # 使用现有CrossRef客户端
            crossref_data = self.crossref_client.get_metadata_by_doi(doi)
            
            if not crossref_data:
                return ProcessorResult(
                    success=False,
                    error="CrossRef: DOI not found",
                    source=self.name
                )
            
            # 转换为标准元数据格式
            metadata = self._convert_crossref_to_metadata(crossref_data)
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=crossref_data,
                confidence=0.95,  # DOI查询置信度很高
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"CrossRef DOI查询失败: {e}")
            return ProcessorResult(
                success=False,
                error=f"CrossRef DOI查询失败: {str(e)}",
                source=self.name
            )
    
    async def _process_by_title(
        self, 
        title: str, 
        year: Optional[int] = None
    ) -> ProcessorResult:
        """
        通过标题搜索CrossRef元数据。
        
        使用直接API调用 + 简化的过滤逻辑。
        
        Args:
            title: 论文标题
            year: 可选的发表年份
            
        Returns:
            ProcessorResult with 搜索结果
        """
        try:
            # 1. 使用直接API进行宽松搜索
            candidates = await self._search_crossref_by_title_direct(title, limit=10)
            
            if not candidates:
                return ProcessorResult(
                    success=False,
                    error="CrossRef: No search results found",
                    source=self.name
                )
            
            logger.info(f"🔍 CrossRef返回{len(candidates)}个候选结果")
            
            # 2. 使用统一标题匹配工具进行过滤
            filtered_results = TitleMatchingUtils.filter_crossref_candidates(
                target_title=title,
                candidates=candidates,
                similarity_threshold=0.8  # 使用相对宽松的阈值
            )
            
            if not filtered_results:
                return ProcessorResult(
                    success=False,
                    error="CrossRef: No results passed similarity filter",
                    source=self.name
                )
            
            # 3. 选择最佳匹配（优先考虑年份）
            best_candidate, similarity_score = self._select_best_candidate(
                filtered_results, target_year=year
            )
            
            logger.info(f"✅ 选择最佳匹配: 相似度={similarity_score:.3f}")
            
            # 4. 转换为标准元数据格式
            metadata = self._convert_crossref_to_metadata(best_candidate)
            
            # 5. 调整置信度（基于相似度）
            confidence = min(0.9, similarity_score * 0.9)  # 最高0.9，基于相似度调整
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=best_candidate,
                confidence=confidence,
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"CrossRef标题搜索失败: {e}")
            return ProcessorResult(
                success=False,
                error=f"CrossRef标题搜索失败: {str(e)}",
                source=self.name
            )
    
    async def _search_crossref_by_title_direct(
        self, 
        title: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        直接使用CrossRef API进行宽松的标题搜索。
        
        避免客户端的严格匹配，使用query.title参数。
        
        Args:
            title: 搜索标题
            limit: 最大结果数量
            
        Returns:
            CrossRef结果列表
        """
        try:
            # 🆕 使用query.title参数而不是title:"..."严格匹配
            title_encoded = quote(title)
            url = f"https://api.crossref.org/works?query.title={title_encoded}&rows={limit}"
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "LiteratureParser/1.0"
            }
            
            logger.debug(f"CrossRef搜索URL: {url[:100]}...")
            
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                headers=headers,
                timeout=20
            )
            
            if response.status_code != 200:
                logger.warning(f"CrossRef API返回状态码: {response.status_code}")
                return []
            
            data = response.json()
            items = data.get('message', {}).get('items', [])
            
            logger.info(f"✅ CrossRef直接搜索返回{len(items)}个结果")
            
            # 记录前几个结果的标题用于调试
            for i, item in enumerate(items[:3]):
                item_title = ""
                if item.get('title'):
                    if isinstance(item['title'], list) and item['title']:
                        item_title = item['title'][0]
                    elif isinstance(item['title'], str):
                        item_title = item['title']
                logger.debug(f"   结果{i+1}: '{item_title[:60]}...'")
            
            return items
            
        except Exception as e:
            logger.error(f"CrossRef直接搜索失败: {e}")
            return []
    
    def _select_best_candidate(
        self, 
        filtered_results: List[Tuple[Dict[str, Any], float]], 
        target_year: Optional[int] = None
    ) -> Tuple[Dict[str, Any], float]:
        """
        从过滤后的结果中选择最佳候选。
        
        简化的选择逻辑，优先考虑年份匹配。
        
        Args:
            filtered_results: (候选项, 相似度分数) 的列表
            target_year: 目标年份
            
        Returns:
            (最佳候选项, 最终分数)
        """
        if not filtered_results:
            raise ValueError("No filtered results to select from")
        
        best_candidate = None
        best_score = 0.0
        
        for candidate, similarity in filtered_results:
            final_score = similarity
            
            # 年份匹配奖励
            if target_year:
                candidate_year = self._extract_year(candidate)
                if candidate_year:
                    if candidate_year == target_year:
                        final_score += 0.1  # 完全匹配奖励
                        logger.debug(f"年份完全匹配奖励: {candidate_year}")
                    elif abs(candidate_year - target_year) <= 1:
                        final_score += 0.05  # 接近匹配奖励
                        logger.debug(f"年份接近匹配奖励: {candidate_year} vs {target_year}")
            
            if final_score > best_score:
                best_score = final_score
                best_candidate = candidate
        
        return best_candidate, best_score
    
    def _extract_year(self, candidate: Dict[str, Any]) -> Optional[int]:
        """从CrossRef候选项中提取年份"""
        if candidate.get('published-print'):
            return candidate['published-print'].get('date-parts', [[None]])[0][0]
        elif candidate.get('published-online'):
            return candidate['published-online'].get('date-parts', [[None]])[0][0]
        return None
    
    def _convert_crossref_to_metadata(self, crossref_data: Dict[str, Any]) -> MetadataModel:
        """
        将CrossRef原始数据转换为标准的MetadataModel。
        
        复用现有的转换逻辑，保持数据格式一致性。
        
        Args:
            crossref_data: CrossRef原始数据
            
        Returns:
            标准化的MetadataModel
        """
        # 提取标题
        title = "Unknown Title"
        if crossref_data.get("title"):
            if isinstance(crossref_data["title"], list) and crossref_data["title"]:
                title = crossref_data["title"][0]
            elif isinstance(crossref_data["title"], str):
                title = crossref_data["title"]
        
        # 提取作者
        authors = []
        if crossref_data.get("author"):
            for author_data in crossref_data["author"]:
                name_parts = []
                if author_data.get("given"):
                    name_parts.append(author_data["given"])
                if author_data.get("family"):
                    name_parts.append(author_data["family"])
                
                if name_parts:
                    full_name = " ".join(name_parts)
                    authors.append(AuthorModel(name=full_name))
        
        # 提取发表年份
        year = None
        if crossref_data.get("published-print"):
            date_parts = crossref_data["published-print"].get("date-parts", [[]])[0]
            if date_parts:
                year = date_parts[0]
        elif crossref_data.get("published-online"):
            date_parts = crossref_data["published-online"].get("date-parts", [[]])[0]
            if date_parts:
                year = date_parts[0]
        
        # 提取期刊信息
        journal = None
        if crossref_data.get("container-title"):
            if isinstance(crossref_data["container-title"], list) and crossref_data["container-title"]:
                journal = crossref_data["container-title"][0]
            elif isinstance(crossref_data["container-title"], str):
                journal = crossref_data["container-title"]
        
        # 提取摘要
        abstract = crossref_data.get("abstract")
        
        return MetadataModel(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=abstract,
            source_priority=[self.name]
        )


# 自动注册处理器
from ..registry import register_processor
register_processor(CrossRefProcessor)


