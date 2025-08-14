#!/usr/bin/env python3
"""
Semantic Scholar元数据处理器 - Paper Parser 0.2

整合现有的Semantic Scholar客户端，支持DOI、ArXiv ID、paper ID查询和标题搜索。
具备rate limiting处理和智能匹配功能。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from ....models.literature import AuthorModel, MetadataModel
from ....services.semantic_scholar import SemanticScholarClient
from ....services.request_manager import ExternalRequestManager, RequestType
from ....utils.title_matching import TitleMatchingUtils
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class SemanticScholarProcessor(MetadataProcessor):
    """
    Semantic Scholar元数据处理器。
    
    支持多种标识符查询和标题搜索，具备rate limiting处理。
    优先级：3（主要API服务，但稍低于CrossRef）
    """
    
    def __init__(self, settings=None):
        """初始化Semantic Scholar处理器"""
        super().__init__(settings)
        self.semantic_scholar_client = SemanticScholarClient(settings)
        self.request_manager = ExternalRequestManager(settings)
    
    @property
    def name(self) -> str:
        """处理器名称"""
        return "Semantic Scholar"
    
    @property
    def processor_type(self) -> ProcessorType:
        """处理器类型"""
        return ProcessorType.API
    
    @property
    def priority(self) -> int:
        """处理器优先级（主要API服务）"""
        return 3
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        检查是否可以处理给定的标识符。
        
        支持：DOI、ArXiv ID、或有标题的情况下进行搜索。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            True if 可以处理这些标识符
        """
        # 如果有DOI或ArXiv ID，直接可以处理
        if identifiers.doi or identifiers.arxiv_id:
            return True
            
        # 如果有标题，可以进行搜索
        if identifiers.title and len(identifiers.title.strip()) > 10:
            return True
            
        return False
    
    async def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        处理标识符并返回元数据。
        
        逻辑：
        1. 优先标识符查询（DOI > ArXiv ID）
        2. 标题搜索 + 智能匹配
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            ProcessorResult with 成功状态和元数据
        """
        try:
            # 1. 优先DOI查询
            if identifiers.doi:
                logger.info(f"🔍 Semantic Scholar DOI查询: {identifiers.doi}")
                result = await self._process_by_identifier(identifiers.doi, "doi")
                if result.success:
                    return result
                logger.info("DOI查询失败，尝试其他方式...")
            
            # 2. ArXiv ID查询
            if identifiers.arxiv_id:
                logger.info(f"🔍 Semantic Scholar ArXiv查询: {identifiers.arxiv_id}")
                result = await self._process_by_identifier(identifiers.arxiv_id, "arxiv")
                if result.success:
                    return result
                logger.info("ArXiv查询失败，尝试标题搜索...")
            
            # 3. 标题搜索（如果有标题）
            if identifiers.title:
                logger.info(f"🔍 Semantic Scholar标题搜索: '{identifiers.title[:50]}...'")
                result = await self._process_by_title(identifiers.title, identifiers.year)
                if result.success:
                    return result
            
            # 4. 无法处理
            return ProcessorResult(
                success=False,
                error="Semantic Scholar: No valid identifiers or title provided",
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"Semantic Scholar处理器异常: {e}")
            return ProcessorResult(
                success=False,
                error=f"Semantic Scholar处理器异常: {str(e)}",
                source=self.name
            )
    
    async def _process_by_identifier(
        self, 
        identifier: str, 
        id_type: str
    ) -> ProcessorResult:
        """
        通过标识符查询Semantic Scholar元数据。
        
        Args:
            identifier: DOI或ArXiv ID
            id_type: 标识符类型 ("doi" 或 "arxiv")
            
        Returns:
            ProcessorResult with 查询结果
        """
        try:
            # 使用现有Semantic Scholar客户端
            s2_data = self.semantic_scholar_client.get_metadata(identifier, id_type=id_type)
            
            if not s2_data:
                return ProcessorResult(
                    success=False,
                    error=f"Semantic Scholar: {id_type.upper()} not found",
                    source=self.name
                )
            
            # 转换为标准元数据格式
            metadata = self._convert_semantic_scholar_to_metadata(s2_data)
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=s2_data,
                confidence=0.9,  # 标识符查询置信度很高
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"Semantic Scholar {id_type}查询失败: {e}")
            return ProcessorResult(
                success=False,
                error=f"Semantic Scholar {id_type}查询失败: {str(e)}",
                source=self.name
            )
    
    async def _process_by_title(
        self, 
        title: str, 
        year: Optional[int] = None
    ) -> ProcessorResult:
        """
        通过标题搜索Semantic Scholar元数据。
        
        使用search API + 智能匹配。
        
        Args:
            title: 论文标题
            year: 可选的发表年份
            
        Returns:
            ProcessorResult with 搜索结果
        """
        try:
            # 1. 使用search API进行搜索
            search_results = await self._search_semantic_scholar_by_title(title, limit=10)
            
            if not search_results:
                return ProcessorResult(
                    success=False,
                    error="Semantic Scholar: No search results found",
                    source=self.name
                )
            
            logger.info(f"🔍 Semantic Scholar返回{len(search_results)}个候选结果")
            
            # 2. 使用智能匹配找到最佳结果
            best_match, similarity_score = self._find_best_title_match(
                target_title=title,
                target_year=year,
                candidates=search_results
            )
            
            if not best_match or similarity_score < 0.7:  # 相对严格的阈值
                return ProcessorResult(
                    success=False,
                    error="Semantic Scholar: No results passed similarity filter",
                    source=self.name
                )
            
            logger.info(f"✅ 选择最佳匹配: 相似度={similarity_score:.3f}")
            
            # 3. 转换为标准元数据格式
            metadata = self._convert_semantic_scholar_to_metadata(best_match)
            
            # 4. 调整置信度（基于相似度）
            confidence = min(0.85, similarity_score * 0.8)  # 最高0.85，基于相似度调整
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=best_match,
                confidence=confidence,
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"Semantic Scholar标题搜索失败: {e}")
            return ProcessorResult(
                success=False,
                error=f"Semantic Scholar标题搜索失败: {str(e)}",
                source=self.name
            )
    
    async def _search_semantic_scholar_by_title(
        self, 
        title: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        使用Semantic Scholar search API进行标题搜索。
        
        Args:
            title: 搜索标题
            limit: 最大结果数量
            
        Returns:
            Semantic Scholar结果列表
        """
        try:
            # Build search URL
            url = f"https://api.semanticscholar.org/graph/v1/paper/search"
            
            params = {
                "query": title,
                "limit": limit,
                "fields": "paperId,title,year,venue,authors,doi,abstract,externalIds"
            }
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "LiteratureParser/1.0"
            }
            
            logger.debug(f"Semantic Scholar搜索: {title[:50]}...")
            
            response = self.request_manager.get(
                url=url,
                request_type=RequestType.EXTERNAL,
                params=params,
                headers=headers,
                timeout=20
            )
            
            # 特殊处理rate limiting
            if response.status_code == 429:
                logger.warning("Semantic Scholar rate limited, skipping title search")
                return []
            
            if response.status_code != 200:
                logger.warning(f"Semantic Scholar API返回状态码: {response.status_code}")
                return []
            
            data = response.json()
            papers = data.get('data', [])
            
            logger.info(f"✅ Semantic Scholar搜索返回{len(papers)}个结果")
            
            # 记录前几个结果的标题用于调试
            for i, paper in enumerate(papers[:3]):
                paper_title = paper.get('title', '')
                logger.debug(f"   结果{i+1}: '{paper_title[:60]}...'")
            
            return papers
            
        except Exception as e:
            logger.error(f"Semantic Scholar搜索失败: {e}")
            return []
    
    def _find_best_title_match(
        self, 
        target_title: str, 
        target_year: Optional[int], 
        candidates: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        从候选结果中找到最佳标题匹配。
        
        使用统一标题匹配工具进行相似度计算，考虑年份匹配。
        
        Args:
            target_title: 目标标题
            target_year: 目标年份
            candidates: 候选论文列表
            
        Returns:
            (最佳匹配论文, 最终相似度分数)
        """
        if not candidates:
            return None, 0.0
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            candidate_title = candidate.get('title', '')
            if not candidate_title:
                continue
            
            # 计算标题相似度
            similarity = TitleMatchingUtils.calculate_combined_similarity(
                target_title, candidate_title
            )
            
            final_score = similarity
            
            # 年份匹配奖励
            if target_year:
                candidate_year = candidate.get('year')
                if candidate_year:
                    if candidate_year == target_year:
                        final_score += 0.1  # 完全匹配奖励
                        logger.debug(f"年份完全匹配奖励: {candidate_year}")
                    elif abs(candidate_year - target_year) <= 1:
                        final_score += 0.05  # 接近匹配奖励
                        logger.debug(f"年份接近匹配奖励: {candidate_year} vs {target_year}")
            
            logger.debug(f"候选: '{candidate_title[:40]}...' 相似度={similarity:.3f} 最终分数={final_score:.3f}")
            
            if final_score > best_score:
                best_score = final_score
                best_match = candidate
        
        return best_match, best_score
    
    def _convert_semantic_scholar_to_metadata(self, s2_data: Dict[str, Any]) -> MetadataModel:
        """
        将Semantic Scholar原始数据转换为标准的MetadataModel。
        
        Args:
            s2_data: Semantic Scholar原始数据
            
        Returns:
            标准化的MetadataModel
        """
        # 提取标题
        title = s2_data.get("title") or "Unknown Title"
        
        # 提取作者
        authors = []
        for author_data in s2_data.get("authors", []):
            name = author_data.get("name")
            if name:
                authors.append(AuthorModel(
                    name=name,
                    s2_id=author_data.get("authorId")
                ))
        
        # 提取发表年份
        year = s2_data.get("year")
        
        # 提取期刊/会议信息
        journal = s2_data.get("venue") or s2_data.get("journal", {}).get("name")
        
        # 提取摘要
        abstract = s2_data.get("abstract")
        
        # 提取关键词（从fieldsOfStudy）
        keywords = []
        fields_of_study = s2_data.get("fieldsOfStudy", [])
        if fields_of_study:
            keywords = [field for field in fields_of_study if isinstance(field, str)]
        
        return MetadataModel(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=abstract,
            keywords=keywords,
            source_priority=[self.name]
        )


# 自动注册处理器
from ..registry import register_processor
register_processor(SemanticScholarProcessor)


