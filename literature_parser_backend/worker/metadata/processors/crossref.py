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
from ....utils.title_matching import TitleMatchingUtils, MatchingMode
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class CrossRefProcessor(MetadataProcessor):
    """
    CrossRef元数据处理器。
    
    整合现有的DOI查询和标题搜索功能，使用精确匹配模式避免错误关联。
    优先级：5（主要API服务之一）
    
    特点：
    - DOI查询：最高精度
    - 标题搜索：使用STRICT模式，只接受极高相似度匹配（>98%）
    - 避免匹配相似但错误的论文（如"Is Attention All You Need?"）
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
        
        支持：DOI直接查询，或有标题+作者的精确搜索。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            True if 可以处理这些标识符
        """
        # 如果有DOI，直接可以处理
        if identifiers.doi:
            return True
            
        # 🆕 精确搜索：需要标题+作者组合，避免模糊搜索
        if (identifiers.title and len(identifiers.title.strip()) > 10 and 
            identifiers.authors and len(identifiers.authors) > 0):
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
            
            # 2. 精确搜索（标题+作者）
            if identifiers.title and identifiers.authors:
                logger.info(f"🔍 CrossRef精确搜索: '{identifiers.title[:50]}...' + {len(identifiers.authors)}个作者")
                result = await self._process_by_title_and_author(
                    identifiers.title, identifiers.authors, identifiers.year
                )
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
    
    async def _process_by_title_and_author(
        self, 
        title: str, 
        authors: List[str],
        year: Optional[int] = None
    ) -> ProcessorResult:
        """
        通过标题+作者精确搜索CrossRef元数据。
        
        使用组合查询参数避免百万级模糊搜索。
        
        Args:
            title: 论文标题
            authors: 作者列表
            year: 可选的发表年份
            
        Returns:
            ProcessorResult with 搜索结果
        """
        try:
            # 1. 使用精确组合搜索
            candidates = await self._search_crossref_precise(title, authors, year, limit=10)
            
            if not candidates:
                return ProcessorResult(
                    success=False,
                    error="CrossRef: No precise search results found",
                    source=self.name
                )
            
            logger.info(f"🔍 CrossRef精确搜索返回{len(candidates)}个候选结果")
            
            # 2. 由于是精确搜索，使用较宽松的匹配模式
            filtered_results = TitleMatchingUtils.filter_crossref_candidates(
                target_title=title,
                candidates=candidates,
                mode=MatchingMode.STANDARD  # 🆕 精确搜索后可用标准模式
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

            # 提取DOI
            new_doi = best_candidate.get("DOI")
            new_identifiers = {"doi": new_doi} if new_doi else None
            
            # 5. 调整置信度（精确搜索置信度更高）
            confidence = min(0.95, similarity_score * 0.95)  # 🆕 精确搜索置信度更高
            
            return ProcessorResult(
                success=True,
                metadata=metadata,
                raw_data=best_candidate,
                confidence=confidence,
                source=self.name,
                new_identifiers=new_identifiers
            )
            
        except Exception as e:
            logger.error(f"CrossRef精确搜索失败: {e}")
            return ProcessorResult(
                success=False,
                error=f"CrossRef精确搜索失败: {str(e)}",
                source=self.name
            )

    # async def _process_by_title(
    #     self, 
    #     title: str, 
    #     year: Optional[int] = None
    # ) -> ProcessorResult:
    #     """
    #     通过标题搜索CrossRef元数据。
        
    #     使用直接API调用 + 简化的过滤逻辑。
        
    #     Args:
    #         title: 论文标题
    #         year: 可选的发表年份
            
    #     Returns:
    #         ProcessorResult with 搜索结果
    #     """
    #     try:
    #         # 1. 使用直接API进行宽松搜索
    #         candidates = await self._search_crossref_by_title_direct(title, limit=10)
            
    #         if not candidates:
    #             return ProcessorResult(
    #                 success=False,
    #                 error="CrossRef: No search results found",
    #                 source=self.name
    #             )
            
    #         logger.info(f"🔍 CrossRef返回{len(candidates)}个候选结果")
            
    #         # 2. 使用统一标题匹配工具进行精确过滤
    #         filtered_results = TitleMatchingUtils.filter_crossref_candidates(
    #             target_title=title,
    #             candidates=candidates,
    #             mode=MatchingMode.STRICT  # 🆕 使用精确模式，避免错误匹配
    #         )
            
    #         if not filtered_results:
    #             return ProcessorResult(
    #                 success=False,
    #                 error="CrossRef: No results passed similarity filter",
    #                 source=self.name
    #             )
            
    #         # 3. 选择最佳匹配（优先考虑年份）
    #         best_candidate, similarity_score = self._select_best_candidate(
    #             filtered_results, target_year=year
    #         )
            
    #         logger.info(f"✅ 选择最佳匹配: 相似度={similarity_score:.3f}")
            
    #         # 4. 转换为标准元数据格式
    #         metadata = self._convert_crossref_to_metadata(best_candidate)

    #         # 提取DOI
    #         new_doi = best_candidate.get("DOI")
    #         new_identifiers = {"doi": new_doi} if new_doi else None
            
    #         # 5. 调整置信度（基于相似度）
    #         confidence = min(0.9, similarity_score * 0.9)  # 最高0.9，基于相似度调整
            
    #         return ProcessorResult(
    #             success=True,
    #             metadata=metadata,
    #             raw_data=best_candidate,
    #             confidence=confidence,
    #             source=self.name,
    #             new_identifiers=new_identifiers  # 传递新发现的DOI
    #         )
            
    #     except Exception as e:
    #         logger.error(f"CrossRef标题搜索失败: {e}")
    #         return ProcessorResult(
    #             success=False,
    #             error=f"CrossRef标题搜索失败: {str(e)}",
    #             source=self.name
    #         )
    
    async def _search_crossref_precise(
        self, 
        title: str, 
        authors: List[str],
        year: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        使用CrossRef API进行精确搜索。
        
        组合标题、作者和年份参数，避免百万级模糊搜索。
        
        Args:
            title: 论文标题
            authors: 作者列表
            year: 发表年份
            limit: 最大结果数量
            
        Returns:
            CrossRef结果列表
        """
        try:
            # 🆕 构建精确搜索参数（使用CrossRef支持的参数格式）
            params = []
            
            # 选择主要作者（通常是第一作者或最知名作者）
            primary_author = self._select_primary_author(authors)
            if primary_author:
                # 提取姓氏用于搜索
                author_surname = self._extract_surname(primary_author)
                if author_surname:
                    params.append(f"query.author={quote(author_surname)}")
            
            # 🆕 使用通用query参数而不是query.title
            title_keywords = self._extract_title_keywords(title)
            if title_keywords:
                params.append(f"query={quote(title_keywords)}")
            
            # 🆕 暂时跳过年份限制，因为CrossRef API不支持这些参数
            # 年份匹配将在后续的过滤阶段进行
            
            # 构建URL
            url = f"https://api.crossref.org/works?{'&'.join(params)}&rows={limit}"
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "LiteratureParser/1.0"
            }
            
            logger.info(f"🎯 CrossRef精确搜索: 作者={primary_author}, 标题关键词={title_keywords}")
            logger.debug(f"CrossRef精确搜索URL: {url[:100]}...")
            
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
            total_results = data.get('message', {}).get('total-results', 0)
            
            logger.info(f"✅ CrossRef精确搜索返回{len(items)}个结果 (总数: {total_results})")
            
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
            logger.error(f"CrossRef精确搜索失败: {e}")
            return []
    
    def _select_primary_author(self, authors: List[str]) -> Optional[str]:
        """选择主要作者用于搜索"""
        if not authors:
            return None
        # 简单策略：选择第一作者
        return authors[0] if authors else None
    
    def _extract_surname(self, author_name: str) -> Optional[str]:
        """从作者姓名中提取姓氏"""
        if not author_name:
            return None
        # 简单策略：假设最后一个词是姓氏
        parts = author_name.strip().split()
        return parts[-1] if parts else None
    
    def _extract_title_keywords(self, title: str, max_words: int = 3) -> str:
        """从标题中提取关键词，避免过度模糊搜索"""
        if not title:
            return ""
        
        # 移除常见停用词
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                    'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being'}
        
        words = [word.strip('.,!?;:()[]{}') for word in title.lower().split()]
        keywords = [word for word in words if len(word) > 3 and word not in stopwords]
        
        # 选择前几个关键词
        selected_keywords = keywords[:max_words]
        return ' '.join(selected_keywords)

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
        
        # 🔧 关键修复：提取 DOI 信息
        doi = crossref_data.get("DOI")
        
        # 🔧 关键修复：提取其他标识符信息
        external_ids = {}
        if doi:
            external_ids["DOI"] = doi
        
        # 检查是否有 ArXiv ID 或其他标识符
        if crossref_data.get("URL"):
            url = crossref_data["URL"]
            if "arxiv.org" in url.lower():
                # 尝试从URL中提取ArXiv ID
                import re
                arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/([^/?]+)', url, re.IGNORECASE)
                if arxiv_match:
                    external_ids["ArXiv"] = arxiv_match.group(1)
        
        return MetadataModel(
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=abstract,
            doi=doi,  # 🔧 添加 DOI 字段
            external_ids=external_ids if external_ids else None,  # 🔧 添加外部标识符
            source_priority=[self.name]
        )


# 自动注册处理器
from ..registry import register_processor
register_processor(CrossRefProcessor)

