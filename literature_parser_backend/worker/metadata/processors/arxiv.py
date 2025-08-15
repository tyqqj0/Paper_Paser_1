#!/usr/bin/env python3
"""
ArXiv元数据处理器 - Paper Parser 0.2

专门处理ArXiv论文的元数据获取和增强。
支持直接获取和现有metadata的增强模式。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ....models.literature import AuthorModel, MetadataModel
from ....services.arxiv_api import ArXivAPIClient
from ....utils.title_matching import TitleMatchingUtils
from ..base import IdentifierData, MetadataProcessor, ProcessorResult, ProcessorType

logger = logging.getLogger(__name__)


class ArXivProcessor(MetadataProcessor):
    """
    ArXiv元数据处理器。
    
    专门处理ArXiv论文，支持直接获取和增强模式。
    优先级：10（中等优先级，主要用作增强）
    """
    
    def __init__(self, settings=None):
        """初始化ArXiv处理器"""
        super().__init__(settings)
        self.arxiv_client = ArXivAPIClient(settings)
    
    @property
    def name(self) -> str:
        """处理器名称"""
        return "ArXiv Official API"
    
    @property
    def processor_type(self) -> ProcessorType:
        """处理器类型"""
        return ProcessorType.API
    
    @property
    def priority(self) -> int:
        """处理器优先级（中等优先级，主要用作增强）"""
        return 10
    
    def can_handle(self, identifiers: IdentifierData) -> bool:
        """
        检查是否可以处理给定的标识符。
        
        可以处理ArXiv ID或标题搜索。
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            True if 有ArXiv ID或标题可以处理
        """
        return bool(identifiers.arxiv_id) or bool(identifiers.title)
    
    async def process(self, identifiers: IdentifierData) -> ProcessorResult:
        """
        处理标识符并返回元数据。
        
        ArXiv处理器支持两种模式：
        1. ArXiv ID直接查询
        2. 标题搜索（适用于NeurIPS等场景）
        
        Args:
            identifiers: 标准化的标识符数据
            
        Returns:
            ProcessorResult with 成功状态和元数据
        """
        try:
            # 优先使用ArXiv ID
            if identifiers.arxiv_id:
                return await self._process_by_arxiv_id(identifiers)
            elif identifiers.title:
                return await self._process_by_title(identifiers)
            else:
                return ProcessorResult(
                    success=False,
                    error="ArXiv: No ArXiv ID or title provided",
                    source=self.name
                )
            
        except Exception as e:
            logger.error(f"ArXiv处理器异常: {e}")
            return ProcessorResult(
                success=False,
                error=f"ArXiv处理器异常: {str(e)}",
                source=self.name
            )
    
    async def _process_by_arxiv_id(self, identifiers: IdentifierData) -> ProcessorResult:
        """通过ArXiv ID处理"""
        logger.info(f"🔍 ArXiv API查询: {identifiers.arxiv_id}")
        
        # 获取ArXiv数据
        arxiv_data = self.arxiv_client.get_metadata(identifiers.arxiv_id)
        
        if not arxiv_data:
            return ProcessorResult(
                success=False,
                error="ArXiv: No metadata found",
                source=self.name
            )
        
        # 转换为标准MetadataModel
        arxiv_metadata = self.arxiv_client.convert_to_metadata_model(arxiv_data)
        
        # 检查是否有现有metadata需要增强
        existing_metadata = self._extract_existing_metadata(identifiers)
        
        if existing_metadata:
            # 增强模式：合并现有metadata和ArXiv数据
            enhanced_metadata = self._enhance_metadata(existing_metadata, arxiv_metadata)
            confidence = 0.75  # 增强模式置信度稍低
            logger.info("✅ ArXiv数据用于增强现有metadata")
        else:
            # 直接模式：使用ArXiv数据作为主要来源
            enhanced_metadata = arxiv_metadata
            confidence = 0.85  # 直接使用ArXiv数据置信度较高
            logger.info("✅ ArXiv数据作为主要metadata来源")
        
        return ProcessorResult(
            success=True,
            metadata=enhanced_metadata,
            raw_data=arxiv_data,
            confidence=confidence,
            source=self.name
        )
    
    async def _process_by_title(self, identifiers: IdentifierData) -> ProcessorResult:
        """通过标题搜索ArXiv"""
        logger.info(f"🔍 ArXiv标题搜索: {identifiers.title}")
        
        # 搜索ArXiv
        search_results = self.arxiv_client.search_by_title(identifiers.title, max_results=5)
        
        if not search_results:
            return ProcessorResult(
                success=False,
                error="ArXiv: No search results found",
                source=self.name
            )
        
        logger.info(f"🔍 ArXiv返回{len(search_results)}个候选结果")
        
        # 使用智能匹配找到最佳结果
        best_match, similarity_score = self._find_best_title_match(
            target_title=identifiers.title,
            target_year=identifiers.year,
            candidates=search_results
        )
        
        if not best_match or similarity_score < 0.7:  # 相对严格的阈值
            return ProcessorResult(
                success=False,
                error="ArXiv: No results passed similarity filter",
                source=self.name
            )
        
        logger.info(f"✅ 选择最佳匹配: 相似度={similarity_score:.3f}")
        
        # 转换为标准元数据格式
        arxiv_metadata = self.arxiv_client.convert_to_metadata_model(best_match)
        
        # 调整置信度（基于相似度）
        confidence = min(0.8, similarity_score * 0.7)  # 搜索模式置信度稍低
        
        return ProcessorResult(
            success=True,
            metadata=arxiv_metadata,
            raw_data=best_match,
            confidence=confidence,
            source=self.name
        )
    
    def _extract_existing_metadata(self, identifiers: IdentifierData) -> Optional[MetadataModel]:
        """
        从标识符数据中提取现有的metadata（如果有）。
        
        这个方法检查source_data中是否有现有的metadata需要增强。
        
        Args:
            identifiers: 标识符数据
            
        Returns:
            现有的MetadataModel或None
        """
        # 检查source_data中是否有现有的metadata
        if identifiers.source_data:
            # 这里可以根据实际情况检查是否有预处理的metadata
            # 目前简化处理，主要基于标题和年份判断
            if identifiers.title:
                # 构建一个简单的现有metadata
                return MetadataModel(
                    title=identifiers.title,
                    year=identifiers.year,
                    authors=[],  # 空的作者列表，等待增强
                    abstract=None,  # 空的摘要，等待增强
                    journal=identifiers.venue
                )
        
        return None
    
    def _enhance_metadata(
        self, 
        existing_metadata: MetadataModel, 
        arxiv_metadata: MetadataModel
    ) -> MetadataModel:
        """
        使用ArXiv数据增强现有metadata。
        
        增强策略：
        1. 如果现有字段为空，使用ArXiv数据填充
        2. 如果现有标题质量差，替换为ArXiv标题
        3. 始终使用ArXiv的摘要（通常质量很高）
        4. 合并关键词
        
        Args:
            existing_metadata: 现有的metadata
            arxiv_metadata: ArXiv的metadata
            
        Returns:
            增强后的MetadataModel
        """
        logger.info("🔧 开始增强现有metadata...")
        
        # 复制现有metadata作为基础
        enhanced = MetadataModel(
            title=existing_metadata.title,
            authors=existing_metadata.authors.copy() if existing_metadata.authors else [],
            year=existing_metadata.year,
            journal=existing_metadata.journal,
            abstract=existing_metadata.abstract,
            keywords=existing_metadata.keywords.copy() if existing_metadata.keywords else [],
            source_priority=existing_metadata.source_priority.copy() if existing_metadata.source_priority else []
        )
        
        # 1. 增强标题（如果现有标题质量差）
        if self._needs_title_enhancement(existing_metadata.title, arxiv_metadata.title):
            enhanced.title = arxiv_metadata.title
            logger.info(f"✅ 标题增强: '{existing_metadata.title}' -> '{arxiv_metadata.title}'")
        
        # 2. 增强摘要（ArXiv摘要通常质量很高）
        if not enhanced.abstract and arxiv_metadata.abstract:
            enhanced.abstract = arxiv_metadata.abstract
            logger.info("✅ 摘要增强: 添加ArXiv摘要")
        elif arxiv_metadata.abstract and len(arxiv_metadata.abstract) > len(enhanced.abstract or ""):
            # 如果ArXiv摘要更长，可能质量更好
            enhanced.abstract = arxiv_metadata.abstract
            logger.info("✅ 摘要增强: 替换为更详细的ArXiv摘要")
        
        # 3. 增强作者（如果现有作者为空）
        if not enhanced.authors and arxiv_metadata.authors:
            enhanced.authors = arxiv_metadata.authors
            logger.info(f"✅ 作者增强: 添加{len(arxiv_metadata.authors)}个作者")
        
        # 4. 增强年份（如果现有年份为空）
        if not enhanced.year and arxiv_metadata.year:
            enhanced.year = arxiv_metadata.year
            logger.info(f"✅ 年份增强: 添加年份{arxiv_metadata.year}")
        
        # 5. 增强期刊信息（如果现有期刊为空，并且ArXiv有期刊引用）
        if not enhanced.journal and arxiv_metadata.journal:
            enhanced.journal = arxiv_metadata.journal
            logger.info(f"✅ 期刊增强: 添加期刊信息")
        
        # 6. 合并关键词
        if arxiv_metadata.keywords:
            existing_keywords = set(enhanced.keywords)
            new_keywords = [kw for kw in arxiv_metadata.keywords if kw not in existing_keywords]
            if new_keywords:
                enhanced.keywords.extend(new_keywords)
                logger.info(f"✅ 关键词增强: 添加{len(new_keywords)}个新关键词")
        
        # 7. 更新source_priority
        enhanced.source_priority.append(f"{self.name} (enhancement)")
        
        return enhanced
    
    def _needs_title_enhancement(self, existing_title: str, arxiv_title: str) -> bool:
        """
        判断是否需要标题增强。
        
        增强条件：
        1. 现有标题为空或默认值
        2. 现有标题包含"Processing:"等临时文本
        3. 现有标题明显质量差（太短等）
        
        Args:
            existing_title: 现有标题
            arxiv_title: ArXiv标题
            
        Returns:
            是否需要增强
        """
        if not existing_title or not arxiv_title:
            return bool(arxiv_title)
        
        # 检查是否是默认或临时标题
        poor_title_indicators = [
            "Unknown Title",
            "Processing:",
            "Extracting:",
            "Loading...",
            "Error:",
            "N/A"
        ]
        
        for indicator in poor_title_indicators:
            if indicator in existing_title:
                return True
        
        # 检查标题长度（太短可能质量差）
        if len(existing_title.strip()) < 10:
            return True
        
        # 检查是否主要是符号或数字（可能是解析错误）
        import re
        if re.match(r'^[\d\s\-\.]+$', existing_title.strip()):
            return True
        
        return False
    
    def _find_best_title_match(
        self, 
        target_title: str, 
        target_year: Optional[int], 
        candidates: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        从候选结果中找到最佳标题匹配
        
        Args:
            target_title: 目标标题
            target_year: 目标年份（可选）
            candidates: 候选论文列表
            
        Returns:
            (最佳匹配的论文, 相似度分数)
        """
        if not candidates:
            return None, 0.0
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            candidate_title = candidate.get('title', '')
            candidate_year = candidate.get('year')
            
            if not candidate_title:
                continue
            
            # 计算标题相似度
            title_similarity = TitleMatchingUtils.calculate_similarity(
                target_title, 
                candidate_title
            )
            
            # 年份匹配加分
            year_bonus = 0.0
            if target_year and candidate_year:
                if target_year == candidate_year:
                    year_bonus = 0.1  # 完全匹配
                elif abs(target_year - candidate_year) <= 1:
                    year_bonus = 0.05  # 相近年份
            
            total_score = title_similarity + year_bonus
            
            logger.debug(f"候选匹配: '{candidate_title}' - 相似度: {title_similarity:.3f}, 年份加分: {year_bonus:.3f}, 总分: {total_score:.3f}")
            
            if total_score > best_score:
                best_score = total_score
                best_match = candidate
        
        return best_match, best_score


# 自动注册处理器
from ..registry import register_processor
register_processor(ArXivProcessor)


