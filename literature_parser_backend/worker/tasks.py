"""
Celery tasks for literature processing.

This module contains the core literature processing task that implements
the intelligent hybrid workflow for gathering metadata and references.
"""

import asyncio
import hashlib
import logging
# from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from celery import Task, current_task

from ..db.dao import LiteratureDAO
from ..db.neo4j import close_task_connection, create_task_connection
from ..models.literature import (
    IdentifiersModel,
    LiteratureModel,
    MetadataModel,
)
from ..models.task import (
    TaskExecutionStatus,
    TaskResultType,
)
from ..services import GrobidClient
from ..services.lid_generator import LIDGenerator
from ..db.alias_dao import AliasDAO
from ..models.alias import AliasType, extract_aliases_from_source
from .execution.smart_router import SmartRouter
from ..utils.title_matching import MatchingMode, TitleMatchingUtils
from .celery_app import celery_app
from .content_fetcher import ContentFetcher
from .deduplication import WaterfallDeduplicator
from .metadata.fetcher import MetadataFetcher
from .references_fetcher import ReferencesFetcher
from .utils import (
    convert_grobid_to_metadata,
    extract_authoritative_identifiers,
    update_task_status,
)
# 🆕 导入智能路由器 (替代原有的SmartExecutor)
from .execution.smart_router import SmartRouter

logger = logging.getLogger(__name__)


# ===============================================
# Metadata Quality Assessment
# ===============================================

def _evaluate_metadata_quality(metadata: Optional[MetadataModel], source: str) -> Dict[str, Any]:
    """
    Evaluate metadata quality with strict criteria.
    
    Returns quality assessment including:
    - is_high_quality: bool - True if metadata is complete and reliable
    - is_partial: bool - True if metadata has basic info but missing key fields  
    - quality_score: int - Score from 0-100
    - missing_fields: List[str] - List of missing critical fields
    """
    if not metadata:
        return {
            "is_high_quality": False,
            "is_partial": False, 
            "quality_score": 0,
            "missing_fields": ["title", "authors", "year", "journal", "abstract"],
            "assessment": "No metadata available"
        }
    
    # Check if this is just fallback data (not from external APIs)
    is_fallback_only = (
        hasattr(metadata, 'source_priority') and 
        metadata.source_priority and 
        len(metadata.source_priority) == 1 and 
        "fallback" in metadata.source_priority[0].lower()
    )
    
    missing_fields = []
    quality_score = 0
    
    # 🎯 Core Requirements Assessment
    
    # Title (Essential - 25 points)
    # 🛡️ 检查是否是解析失败的标识
    failed_title_indicators = [
        "Unknown Title",
        "Processing...",
        "Extracting...",
        "Loading...",
        "Error:",
        "N/A"
    ]
    
    is_parsing_failed = any(indicator in (metadata.title or "") for indicator in failed_title_indicators)
    
    if not metadata.title or is_parsing_failed:
        missing_fields.append("title")
        if is_parsing_failed:
            # 如果检测到解析失败标识，直接返回特殊评估结果
            return {
                "is_high_quality": False,
                "is_partial": False,
                "quality_score": 0,
                "missing_fields": ["title", "authors", "year", "journal", "abstract"],
                "assessment": "parsing_failed",
                "is_fallback_only": False,
                "is_parsing_failed": True,
                "failed_indicators": [indicator for indicator in failed_title_indicators if indicator in (metadata.title or "")]
            }
    else:
        quality_score += 25
        
    # Authors (Critical - 25 points)  
    if not metadata.authors or len(metadata.authors) == 0:
        missing_fields.append("authors")
    else:
        quality_score += 25
        
    # Publication Year (Important - 20 points)
    if not metadata.year:
        missing_fields.append("year") 
    else:
        quality_score += 20
        
    # Journal/Venue (Important - 15 points)
    if not metadata.journal:
        missing_fields.append("journal")
    else:
        quality_score += 15
        
    # Abstract (Valuable - 10 points)
    if not metadata.abstract:
        missing_fields.append("abstract")
    else:
        quality_score += 10
        
    # Keywords (Nice-to-have - 5 points)
    if not metadata.keywords or len(metadata.keywords) == 0:
        missing_fields.append("keywords")
    else:
        quality_score += 5
        
    # 🎯 Quality Thresholds
    
    # Penalize fallback-only data severely
    if is_fallback_only:
        quality_score = min(quality_score, 30)  # Cap at 30% for fallback data
        
    # High Quality: Complete metadata with all essential fields (80%+)
    is_high_quality = (
        quality_score >= 80 and 
        not is_fallback_only and
        "title" not in missing_fields and 
        "authors" not in missing_fields
    )
    
    # Partial Quality: Has title and at least one other important field (40-79%)
    is_partial = (
        quality_score >= 40 and 
        not is_high_quality and
        "title" not in missing_fields
    )
    
    assessment = "high_quality" if is_high_quality else ("partial" if is_partial else "failed")
    
    logger.info(
        f"Metadata quality assessment: {assessment} (score: {quality_score}/100, "
        f"source: {source}, fallback_only: {is_fallback_only}, "
        f"missing: {missing_fields})"
    )
    
    return {
        "is_high_quality": is_high_quality,
        "is_partial": is_partial,
        "quality_score": quality_score, 
        "missing_fields": missing_fields,
        "assessment": assessment,
        "is_fallback_only": is_fallback_only
    }


# ===============================================
# Task Status Management
# ===============================================


class TaskStatusManager:
    """任务状态管理器 - 分离任务执行状态和文献处理状态"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.url_validation_info = None

    def update_task_progress(self, stage: str, progress: int, literature_id: str = None):
        """更新Celery任务进度（轻量级信息）"""
        meta = {
            "literature_id": literature_id,
            "current_stage": stage,
            "progress": progress
        }

        # 如果有URL验证信息，添加到meta中
        if self.url_validation_info:
            meta.update({
                "url_validation_status": self.url_validation_info.get("status"),
                "url_validation_error": self.url_validation_info.get("error"),
                "original_url": self.url_validation_info.get("original_url"),
            })

        current_task.update_state(
            state="PROGRESS",
            meta=meta
        )

    def set_url_validation_info(self, url_validation_info: Dict[str, Any]):
        """设置URL验证信息"""
        self.url_validation_info = url_validation_info

    def fail_task_with_url_validation_error(self, error_info, original_url: str = None):
        """因URL验证失败而终止任务"""
        # 不使用FAILURE状态，而是使用PROGRESS状态来避免Celery序列化问题
        meta = {
            "error": error_info.error_message,
            "error_type": error_info.error_type,
            "error_category": error_info.error_category,
            "url_validation_status": "failed",
            "url_validation_error": error_info.error_message,
            "original_url": original_url,
            "url_validation_details": error_info.url_validation_details,
            "task_failed": True,  # 标记任务失败
        }

        current_task.update_state(
            state="PROGRESS",  # 使用PROGRESS而不是FAILURE
            meta=meta
        )

    def complete_task(self, result_type: TaskResultType, literature_id: str) -> Dict[str, Any]:
        """完成任务并返回结果"""
        result = {
            "status": TaskExecutionStatus.COMPLETED,
            "result_type": result_type,
            "literature_id": literature_id
        }

        # 如果有URL验证信息，添加到结果中
        if self.url_validation_info:
            result.update({
                "url_validation_status": self.url_validation_info.get("status"),
                "original_url": self.url_validation_info.get("original_url"),
            })

        return result

    def fail_task(self, error_message: str, literature_id: str = None) -> Dict[str, Any]:
        """任务失败"""
        return {
            "status": TaskExecutionStatus.FAILED,
            "error_message": error_message,
            "literature_id": literature_id
        }


# ===============================================
# Helper Functions for Deduplication and Fetching
# ===============================================


async def _deduplicate_literature(
    identifiers: IdentifiersModel,
    source_data: Dict[str, Any],
    dao: LiteratureDAO,
    task_id: str,
) -> Tuple[Optional[str], Optional[MetadataModel], Optional[bytes]]:
    """
    Execute the deduplication waterfall logic.

    Returns a tuple of:
    - Existing literature model if found
    - Prefetched metadata from GROBID if any
    - PDF content if downloaded
    """
    # 1. Direct identifier check (DOI, ArXiv ID) with failure cleanup
    if identifiers.doi:
        if literature := await dao.find_by_doi(identifiers.doi):
            # Check if this is a failed literature
            if literature.task_info and literature.task_info.status == "failed":
                logger.info(
                    f"Found failed literature with DOI {identifiers.doi}, cleaning up...",
                )
                await dao.delete_literature(str(literature.id))
                return None, None, None
            return str(literature.id), None, None
    if identifiers.arxiv_id:
        if literature := await dao.find_by_arxiv_id(identifiers.arxiv_id):
            # Check if this is a failed literature
            if literature.task_info and literature.task_info.status == "failed":
                logger.info(
                    f"Found failed literature with ArXiv ID {identifiers.arxiv_id}, cleaning up...",
                )
                await dao.delete_literature(str(literature.id))
                return None, None, None
            return str(literature.id), None, None

    # 2. PDF-based check (Fingerprint, Title)
    pdf_content: Optional[bytes] = None
    prefetched_metadata: Optional[MetadataModel] = None

    if source_data.get("pdf_url"):
        update_task_status("正在下载PDF用于去重", progress=10)
        try:
            from .content_fetcher import ContentFetcher

            content_fetcher = ContentFetcher()
            pdf_content = content_fetcher._download_pdf(source_data["pdf_url"])

            if pdf_content:
                # Generate fingerprint
                fingerprint = hashlib.md5(pdf_content).hexdigest()

                # Check by fingerprint with failure cleanup
                if literature := await dao.find_by_fingerprint(fingerprint):
                    # Check if this is a failed literature
                    if literature.task_info and literature.task_info.status == "failed":
                        logger.info(
                            f"Found failed literature with fingerprint {fingerprint}, cleaning up...",
                        )
                        await dao.delete_literature(str(literature.id))
                    else:
                        return str(literature.id), None, pdf_content

                # Try to extract title with GROBID for title-based deduplication
                try:
                    grobid_client = GrobidClient()
                    parsed_data = grobid_client.process_header_only(pdf_content)
                    prefetched_metadata = convert_grobid_to_metadata(parsed_data)

                    if (
                        prefetched_metadata
                        and prefetched_metadata.title != "Unknown Title"
                    ):
                        if literature := await dao.find_by_title(
                            prefetched_metadata.title,
                        ):
                            # Check if this is a failed literature
                            if (
                                literature.task_info
                                and literature.task_info.status == "failed"
                            ):
                                logger.info(
                                    f"Found failed literature with title {prefetched_metadata.title}, cleaning up...",
                                )
                                await dao.delete_literature(str(literature.id))
                            else:
                                return (
                                    str(literature.id),
                                    prefetched_metadata,
                                    pdf_content,
                                )
                except Exception as e:
                    logger.warning(f"GROBID prefetch failed: {e}")
        except Exception as e:
            logger.warning(f"PDF download/processing failed: {e}")

    return None, prefetched_metadata, pdf_content


async def _record_alias_mappings(
    literature: LiteratureModel,
    source_data: Dict[str, Any],
    dao: LiteratureDAO,
    task_id: str
) -> None:
    """
    Record alias mappings for a successfully created literature.
    
    This function creates mappings between external identifiers and the LID,
    enabling fast future lookups without requiring full processing.
    
    Args:
        literature: The created literature model
        source_data: Original source data from the request
        dao: Database access object
        task_id: Current task ID
    """
    try:
        if not literature.lid:
            logger.warning(f"Task {task_id}: No LID found in literature, skipping alias mapping")
            return
        
        # Create alias DAO from same database connection
        alias_dao = AliasDAO(database=dao.driver)
        
        # Extract aliases from source data
        source_aliases = extract_aliases_from_source(source_data)
        logger.info(f"Task {task_id}: Found {len(source_aliases)} source aliases to map")
        
        # Add aliases from parsed identifiers
        literature_aliases = {}
        
        if literature.identifiers.doi:
            literature_aliases[AliasType.DOI] = literature.identifiers.doi
        
        if literature.identifiers.arxiv_id:
            literature_aliases[AliasType.ARXIV] = literature.identifiers.arxiv_id
            
        if literature.identifiers.pmid:
            literature_aliases[AliasType.PMID] = literature.identifiers.pmid
        
        # Add content URLs if available
        if literature.content.pdf_url:
            literature_aliases[AliasType.PDF_URL] = literature.content.pdf_url
            
        if literature.content.source_page_url:
            literature_aliases[AliasType.SOURCE_PAGE] = literature.content.source_page_url
        
        # Add title if available (for title-based lookups)
        if literature.metadata.title:
            literature_aliases[AliasType.TITLE] = literature.metadata.title
        
        # Combine all aliases
        all_aliases = {**source_aliases, **literature_aliases}
        logger.info(f"Task {task_id}: Total {len(all_aliases)} aliases to create for LID {literature.lid}")
        
        # Batch create all mappings
        if all_aliases:
            created_ids = await alias_dao.batch_create_mappings(
                lid=literature.lid,
                mappings=all_aliases,
                confidence=1.0,
                metadata={
                    "source": "literature_creation",
                    "task_id": task_id,
                    "created_from": "automatic_mapping"
                }
            )
            
            logger.info(
                f"Task {task_id}: Successfully created {len(created_ids)} alias mappings for LID {literature.lid}"
            )
        else:
            logger.warning(f"Task {task_id}: No aliases found to create for LID {literature.lid}")
            
    except Exception as e:
        # Don't fail the entire task if alias creation fails
        logger.error(
            f"Task {task_id}: Failed to create alias mappings for LID {literature.lid if literature else 'unknown'}: {e}",
            exc_info=True
        )


async def _upgrade_matching_unresolved_nodes(
    literature: "LiteratureModel",
    dao: "LiteratureDAO", 
    task_id: str
):
    """
    检查并升级匹配的未解析节点。
    
    当新文献添加时，检查是否有匹配的未解析占位符节点，
    如果有，将这些节点升级为指向真实文献的关系。
    
    Args:
        literature: 新创建的文献模型
        dao: 数据库访问对象
        task_id: 当前任务ID
    """
    try:
        from ..db.relationship_dao import RelationshipDAO
        from ..worker.citation_resolver import CitationResolver
        
        # 创建关系DAO - 使用相同的数据库连接
        relationship_dao = RelationshipDAO(database=dao.driver if hasattr(dao, 'driver') else None)
        
        # 生成匹配候选的LID模式
        matching_patterns = []
        
        # 🎯 新策略：基于标题规范化进行智能匹配，不依赖作者格式差异
        if literature.metadata and literature.metadata.title:
            # 使用标题规范化进行匹配查找
            from ..utils.title_normalization import normalize_title_for_matching
            
            normalized_title = normalize_title_for_matching(literature.metadata.title)
            if normalized_title:
                logger.info(
                    f"Task {task_id}: Searching for unresolved nodes with normalized title: "
                    f"'{normalized_title[:50]}...'"
                )
                
                # 直接查找数据库中匹配的未解析节点
                try:
                    async with relationship_dao._get_session() as session:
                        # 查找标题匹配的未解析节点
                        title_match_query = """
                        MATCH (u:Unresolved)
                        WHERE u.parsed_title IS NOT NULL
                        RETURN u.lid as lid, u.parsed_title as title, u.parsed_year as year
                        """
                        
                        result = await session.run(title_match_query)
                        candidate_nodes = []
                        async for record in result:
                            candidate_title = record["title"]
                            candidate_year = record["year"]
                            candidate_lid = record["lid"]
                            
                            if candidate_title:
                                candidate_normalized = normalize_title_for_matching(candidate_title)
                                
                                # 🎯 匹配条件：标题相同 + 年份相同或相近(±1年，考虑不同数据源的年份差异)
                                title_matches = candidate_normalized == normalized_title
                                year_matches = True  # 默认匹配
                                
                                if literature.metadata.year and candidate_year:
                                    try:
                                        lit_year = int(literature.metadata.year)
                                        cand_year = int(candidate_year)
                                        # 允许±1年的差异（考虑会议/期刊发表时间差异）
                                        year_matches = abs(lit_year - cand_year) <= 1
                                    except (ValueError, TypeError):
                                        year_matches = True  # 年份解析失败时不作为阻断条件
                                
                                if title_matches and year_matches:
                                    candidate_nodes.append({
                                        "lid": candidate_lid,
                                        "title": candidate_title,
                                        "year": candidate_year
                                    })
                                    logger.info(
                                        f"Task {task_id}: Found title match candidate: {candidate_lid} "
                                        f"(year: {candidate_year} vs {literature.metadata.year})"
                                    )
                        
                        # 添加匹配的候选LID
                        for candidate in candidate_nodes:
                            matching_patterns.append(candidate["lid"])
                
                except Exception as e:
                    logger.warning(f"Task {task_id}: Error in title-based matching: {e}")
                    # 继续执行，不因匹配错误中断任务
        
        logger.info(f"Task {task_id}: Searching for unresolved nodes to upgrade: {matching_patterns}")
        
        # 检查每个可能的LID
        upgraded_count = 0
        for pattern_lid in matching_patterns:
            try:
                # 检查是否存在这个未解析节点
                async with relationship_dao._get_session() as session:
                    check_query = """
                    MATCH (unresolved:Unresolved {lid: $pattern_lid})
                    RETURN unresolved.lid as lid, unresolved.parsed_title as title
                    """
                    
                    result = await session.run(check_query, pattern_lid=pattern_lid)
                    record = await result.single()
                    
                    if record:
                        logger.info(f"Task {task_id}: Found matching unresolved node: {pattern_lid} -> {record['title']}")
                        
                        # 执行升级
                        upgrade_stats = await relationship_dao.upgrade_unresolved_to_literature(
                            placeholder_lid=pattern_lid,
                            literature_lid=literature.lid
                        )
                        
                        if upgrade_stats.get("relationships_updated", 0) > 0:
                            upgraded_count += 1
                            logger.info(
                                f"Task {task_id}: ✅ Upgraded {pattern_lid} -> {literature.lid}, "
                                f"updated {upgrade_stats['relationships_updated']} relationships"
                            )
                        else:
                            logger.warning(
                                f"Task {task_id}: ⚠️ Found {pattern_lid} but no relationships to upgrade"
                            )
                    
            except Exception as e:
                logger.warning(f"Task {task_id}: Error checking pattern {pattern_lid}: {e}")
                # 继续检查其他模式
        
        if upgraded_count > 0:
            logger.info(f"Task {task_id}: ✅ Successfully upgraded {upgraded_count} unresolved nodes to literature {literature.lid}")
        else:
            logger.info(f"Task {task_id}: No matching unresolved nodes found for literature {literature.lid}")
        
    except Exception as e:
        logger.error(f"Task {task_id}: Error in unresolved node upgrade: {e}", exc_info=True)
        # 不要因为升级失败而使整个任务失败
        pass


async def _check_and_handle_post_metadata_duplicate(
    dao: "LiteratureDAO",
    identifiers: "IdentifiersModel",
    metadata: "MetadataModel",
    source_data: Dict[str, Any],
    placeholder_lid: str,
    task_id: str,
) -> Optional[str]:
    """
    Checks for duplicates after metadata is fetched and handles them.
    If a duplicate is found, it merges aliases, deletes the placeholder,
    and returns the LID of the existing literature.
    """
    logger.info(f"🕵️‍♂️ [Secondary Dedup] Starting for placeholder {placeholder_lid} with title='{metadata.title}' and DOI='{identifiers.doi}'")
    
    # 🔍 Debug: 详细搜索现有文献
    try:
        # 1. 按标题搜索
        candidates_debug = await dao.find_by_title_fuzzy(metadata.title, limit=10)
        logger.info(f"🔍 [Secondary Dedup] DEBUG - 按标题搜索到 {len(candidates_debug)} 个候选文献")
        for i, cand in enumerate(candidates_debug):
            if cand and cand.metadata:
                logger.info(f"🔍 [Secondary Dedup] DEBUG - 候选 {i+1}: {cand.lid} - '{cand.metadata.title}' (年份: {getattr(cand.metadata, 'year', 'N/A')})")
        
        # 2. 查看数据库中的所有文献（用于调试）
        all_literature_debug = await dao.get_all_literature(limit=20)
        logger.info(f"🔍 [Secondary Dedup] DEBUG - 数据库中总共有 {len(all_literature_debug)} 篇文献:")
        for i, lit in enumerate(all_literature_debug):
            if lit and lit.metadata:
                logger.info(f"🔍 [Secondary Dedup] DEBUG - 数据库文献 {i+1}: {lit.lid} - '{lit.metadata.title}' (年份: {getattr(lit.metadata, 'year', 'N/A')})")
        
        # 3. 检查当前标题和第一个文献的匹配情况（如果存在）
        if all_literature_debug and len(all_literature_debug) > 0:
            first_lit = all_literature_debug[0]
            if first_lit and first_lit.metadata:
                logger.info(f"🔍 [Secondary Dedup] DEBUG - 比较当前标题: '{metadata.title}' 与第一个文献: '{first_lit.metadata.title}'")
                # 使用标题匹配工具进行详细比较
                from ..utils.title_matching import TitleMatchingUtils, MatchingMode
                is_match = TitleMatchingUtils.is_acceptable_match(
                    first_lit.metadata.title, metadata.title, mode=MatchingMode.STRICT
                )
                logger.info(f"🔍 [Secondary Dedup] DEBUG - 严格模式匹配结果: {is_match}")
                is_match_standard = TitleMatchingUtils.is_acceptable_match(
                    first_lit.metadata.title, metadata.title, mode=MatchingMode.STANDARD
                )
                logger.info(f"🔍 [Secondary Dedup] DEBUG - 标准模式匹配结果: {is_match_standard}")
                
    except Exception as e:
        logger.warning(f"🔍 [Secondary Dedup] DEBUG - 检查时出错: {e}")
        import traceback
        logger.warning(f"🔍 [Secondary Dedup] DEBUG - 错误详情: {traceback.format_exc()}")
    existing_lit = None
    # 1. Check by DOI first (most reliable)
    if identifiers and identifiers.doi:
        existing_lit = await dao.find_by_doi(identifiers.doi)

    # 2. If no DOI match, check by title similarity
    if not existing_lit and metadata and metadata.title:
        # Use fuzzy search to get candidates, then a more precise similarity check
        candidates = await dao.find_by_title_fuzzy(metadata.title, limit=5)
        logger.info(f"🕵️‍♂️ [Secondary Dedup] Found {len(candidates)} candidates by fuzzy title search for '{metadata.title}'")
        
        # Filter out the current placeholder to avoid self-matching
        candidates = [cand for cand in candidates if cand.lid != placeholder_lid]
        logger.info(f"🕵️‍♂️ [Secondary Dedup] After filtering out placeholder {placeholder_lid}: {len(candidates)} candidates remain")
        
        # 🔍 Debug: 列出所有候选文献详情
        for i, cand in enumerate(candidates):
            logger.info(f"🕵️‍♂️ [Secondary Dedup]   Candidate {i+1}: LID={cand.lid}, Title='{cand.metadata.title if cand.metadata else 'N/A'}'")
        for cand_lit in candidates:
            if not cand_lit or not cand_lit.metadata or not cand_lit.metadata.title:
                logger.warning(f"🕵️‍♂️ [Secondary Dedup] Skipping invalid candidate: {cand_lit}")
                continue
            
            logger.info(f"🕵️‍♂️ [Secondary Dedup]  - Comparing with candidate {cand_lit.lid} ('{cand_lit.metadata.title}')")
            # Use a standard, balanced matching mode
            is_match = TitleMatchingUtils.is_acceptable_match(
                cand_lit.metadata.title, metadata.title, mode=MatchingMode.STANDARD
            )
            logger.info(f"🕵️‍♂️ [Secondary Dedup]  - Title match result: {is_match}")
            
            if is_match:
                # As an extra precaution, check year difference for non-DOI matches
                if metadata.year and cand_lit.metadata.year:
                    try:
                        year_diff = abs(int(metadata.year) - int(cand_lit.metadata.year))
                        logger.info(f"🕵️‍♂️ [Secondary Dedup]  - Year difference: {year_diff}")
                        if year_diff > 2:  # Allow up to 2 years difference
                            logger.info(f"🕵️‍♂️ [Secondary Dedup]  - Year difference too large, skipping.")
                            continue  # Likely a different version, not a duplicate
                    except (ValueError, TypeError):
                        pass  # Ignore if year is not a valid integer
                
                logger.info(f"✅ [Secondary Dedup] Match found: {cand_lit.lid}")
                existing_lit = cand_lit
                break  # Found a match
    
    if not existing_lit:
        logger.info("🕵️‍♂️ [Secondary Dedup] No duplicate found after all checks.")

    # 3. If a duplicate is found, handle it
    if existing_lit and existing_lit.lid:
        logger.info(
            f"Task {task_id}: Post-metadata duplicate found! "
            f"Placeholder {placeholder_lid} matches existing {existing_lit.lid}."
        )
        
        # Add new source info as alias to the existing literature
        try:
            alias_dao = AliasDAO(database=dao.driver)
            source_aliases = extract_aliases_from_source(source_data)
            if source_aliases:
                await alias_dao.batch_create_mappings(
                    lid=existing_lit.lid,
                    mappings=source_aliases,
                    confidence=1.0,
                    metadata={"source": "post_metadata_deduplication", "task_id": task_id}
                )
                logger.info(f"Task {task_id}: Added new aliases {list(source_aliases.keys())} to existing literature {existing_lit.lid}")
        except Exception as e:
            logger.error(f"Task {task_id}: Failed to add alias to existing literature {existing_lit.lid}: {e}")

        # Delete the placeholder node that is no longer needed
        try:
            await dao.delete_literature(placeholder_lid)
            logger.info(f"Task {task_id}: Deleted placeholder literature {placeholder_lid}.")
        except Exception as e:
            logger.error(f"Task {task_id}: Failed to delete placeholder {placeholder_lid}: {e}")
            
        return existing_lit.lid

    return None


async def _process_literature_async(
    task_id: str,
    source: Dict[str, Any],
) -> Dict[str, Any]:
    """Asynchronous core logic for processing literature."""
    # Create dedicated database connection for this task
    client = None
    try:
        client, database = await create_task_connection()

        # 初始化任务状态管理器
        task_manager = TaskStatusManager(task_id)
        task_manager.update_task_progress("任务开始", 0)

        dao = LiteratureDAO.create_from_task_connection(database)
        
        # 🆕 智能路由系统 - 专注路由选择和数据管道
        url = source.get('url', '')
        
        # 🚀 优化：先用轻量级方法判断是否能处理，避免不必要的SmartRouter实例化
        # 使用单例路由管理器进行快速判断
        from .execution.routing import RouteManager
        route_manager = RouteManager.get_instance()
        route = route_manager.determine_route(url)
        
        # 🔧 修复：所有路由都应该走智能路由，包括standard_waterfall
        logger.info(f"🚀 Task {task_id}: 智能路由启动: {url} -> {route.name}")
        smart_router = SmartRouter(dao)
        
        try:
            router_result = await smart_router.route_and_process(url, source, task_id)
            
            # 检查智能路由结果
            if router_result.get('status') == 'completed':
                logger.info(f"✅ Task {task_id}: 智能路由完成，耗时: {router_result.get('execution_time', 0):.2f}s")
                
                # 转换为标准任务结果格式
                result_type = 'duplicate' if router_result.get('result_type') == 'duplicate' else 'created'
                final_result = task_manager.complete_task(
                    TaskResultType.DUPLICATE if result_type == 'duplicate' else TaskResultType.CREATED,
                    router_result.get('literature_id')
                )
                
                # 添加智能路由的额外信息
                final_result.update({
                    'route_used': router_result.get('route_used'),
                    'processor_used': router_result.get('processor_used'),
                    'execution_time': router_result.get('execution_time')
                })
                
                # 🔧 混合模式：智能路由完成，为传统引用解析准备变量
                if router_result.get('result_type') == 'duplicate':
                    # 重复文献直接返回，无需引用解析
                    return final_result
                else:
                    # 新创建的文献：准备变量，继续执行传统引用解析
                    logger.info(f"🔄 Task {task_id}: 智能路由完成，准备传统引用解析")
                    
                    # 🎯 从智能路由结果中提取必要变量给传统流程使用
                    literature_id = router_result.get('literature_id')  # 这是LID
                    
                    # 🔧 关键修复：提取智能路由中的原始标识符信息
                    router_identifiers = router_result.get('identifiers')
                    
                    # 从DAO获取完整的文献对象
                    try:
                        literature_obj = await dao.find_by_lid(literature_id)
                        if literature_obj:
                            metadata = literature_obj.metadata
                            
                            # 🔧 关键修复：保留原始标识符信息用于引用解析
                            if router_identifiers:
                                # 🔧 处理智能路由返回的标识符格式（可能是字典）
                                from literature_parser_backend.models.literature import IdentifiersModel
                                if isinstance(router_identifiers, dict):
                                    identifiers = IdentifiersModel(
                                        doi=router_identifiers.get('doi'),
                                        arxiv_id=router_identifiers.get('arxiv_id'),
                                        pmid=router_identifiers.get('pmid')
                                    )
                                    logger.info(f"🔗 Task {task_id}: 智能路由字典标识符已转换: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
                                else:
                                    identifiers = router_identifiers
                                    logger.info(f"🔗 Task {task_id}: 使用智能路由原始标识符: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
                            else:
                                # 备选方案：从元数据中提取
                                from literature_parser_backend.models.literature import IdentifiersModel
                                identifiers = IdentifiersModel()
                                if metadata and hasattr(metadata, 'doi') and metadata.doi:
                                    identifiers.doi = metadata.doi
                                logger.info(f"🔗 Task {task_id}: 备选 - 从元数据提取标识符: DOI={identifiers.doi}")
                            
                            # 设置标志表示已完成智能路由
                            smart_router_completed = True
                            smart_router_result = router_result
                            logger.info(f"🔗 Task {task_id}: 准备引用解析，文献: {literature_id}")
                        else:
                            logger.error(f"❌ Task {task_id}: 无法找到刚创建的文献: {literature_id}")
                            return final_result
                    except Exception as e:
                        logger.error(f"❌ Task {task_id}: 获取文献对象失败: {e}")
                        return final_result
                
            elif router_result.get('fallback_to_legacy'):
                logger.warning(f"⚠️ Task {task_id}: 智能路由建议回退: {router_result.get('error')}")
                smart_router_result = router_result  # 保存错误信息
                # 继续执行传统流程
            else:
                logger.error(f"❌ Task {task_id}: 智能路由失败: {router_result.get('error')}")
                smart_router_result = router_result  # 保存错误信息
                # 继续执行传统流程
                    
        except Exception as e:
            logger.error(f"❌ Task {task_id}: 智能路由异常: {e}")
            smart_router_result = {'error': str(e), 'error_type': 'system_error'}  # 保存异常信息
            # 继续执行传统流程
        
        # 📋 传统瀑布流处理逻辑 (保持原有逻辑作为备选方案)
        
        # 🔧 初始化智能路由标志
        smart_router_completed = locals().get('smart_router_completed', False)
        smart_router_result = locals().get('smart_router_result', {})
        
        # 🔧 检查智能路由是否已完成
        if smart_router_completed:
            logger.info(f"🚀 Task {task_id}: 智能路由已完成，跳转到引用解析")
            # 智能路由已完成，跳过去重和元数据获取，直接进入引用解析
            # literature_id 和 metadata 已经在上面准备好了
        else:
            logger.info(f"🔄 Task {task_id}: 开始传统瀑布流处理")





        # 🔧 智能路由和传统流程的统一处理点
        if 'smart_router_completed' in locals() and smart_router_completed:
            # 智能路由已完成，直接使用准备好的变量
            logger.info(f"🎯 Task {task_id}: 使用智能路由结果进行引用解析，LID: {literature_id}")
            
            # 📝 为引用解析准备标识符信息
            if not 'identifiers' in locals():
                # 🔧 关键修复：优先使用原始的去重阶段提取的标识符，而不是创建空的
                try:
                    # 尝试从已完成的智能路由结果中获取标识符
                    if smart_router_result and 'identifiers' in smart_router_result:
                        router_identifiers_dict = smart_router_result['identifiers']
                        
                        # 🔧 关键修复：将字典格式转换为IdentifiersModel对象
                        from literature_parser_backend.models.literature import IdentifiersModel
                        if isinstance(router_identifiers_dict, dict):
                            identifiers = IdentifiersModel(
                                doi=router_identifiers_dict.get('doi'),
                                arxiv_id=router_identifiers_dict.get('arxiv_id'),
                                pmid=router_identifiers_dict.get('pmid')
                            )
                            logger.info(f"🔗 Task {task_id}: 智能路由字典格式标识符已转换: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
                        else:
                            # 如果已经是IdentifiersModel对象，直接使用
                            identifiers = router_identifiers_dict
                            logger.info(f"🔗 Task {task_id}: 使用智能路由结果中的标识符对象")
                    else:
                        # 备选方案：从元数据中提取标识符信息
                        from literature_parser_backend.models.literature import IdentifiersModel
                        identifiers = IdentifiersModel()
                        if metadata:
                            if hasattr(metadata, 'doi') and metadata.doi:
                                identifiers.doi = metadata.doi
                                logger.info(f"🔧 Task {task_id}: 从metadata中提取DOI: {metadata.doi}")
                            if hasattr(metadata, 'external_ids') and metadata.external_ids:
                                if 'ArXiv' in metadata.external_ids:
                                    identifiers.arxiv_id = metadata.external_ids['ArXiv']
                                    logger.info(f"🔧 Task {task_id}: 从metadata中提取ArXiv ID: {metadata.external_ids['ArXiv']}")
                                if 'DOI' in metadata.external_ids and not identifiers.doi:
                                    identifiers.doi = metadata.external_ids['DOI']
                                    logger.info(f"🔧 Task {task_id}: 从external_ids中提取DOI: {metadata.external_ids['DOI']}")
                        logger.info(f"🔗 Task {task_id}: 备选方案 - 从元数据准备标识符")
                except Exception as e:
                    logger.error(f"⚠️ Task {task_id}: 标识符提取失败: {e}")
                    # 最后的备选方案：创建空的标识符
                    from literature_parser_backend.models.literature import IdentifiersModel
                    identifiers = IdentifiersModel()
                
                logger.info(f"🔗 Task {task_id}: 最终标识符准备完成: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
            
            # 🚨 关键修复：设置元数据组件状态为 success，确保引用解析依赖检查通过
            logger.info(f"🔧 Task {task_id}: 为智能路由设置元数据组件状态为 success")
            await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="metadata",
                status="success",
                stage="智能路由元数据获取成功",
                progress=100,
                source="SmartRouter",
                next_action=None,
            )
            
            # 🔍 元数据解析完成后的重复检查
            logger.info(f"🔍 Task {task_id}: 开始元数据解析后的重复检查")
            existing_lit_lid = await _check_and_handle_post_metadata_duplicate(
                dao=dao,
                identifiers=identifiers,
                metadata=metadata,
                source_data=source,
                placeholder_lid=literature_id,
                task_id=task_id
            )
            
            if existing_lit_lid:
                logger.info(f"✅ Task {task_id}: 发现重复文献 {existing_lit_lid}，停止处理并返回已有文献")
                return task_manager.complete_task(TaskResultType.DUPLICATE, existing_lit_lid)
            
            logger.info(f"✅ Task {task_id}: 无重复文献，继续处理流程")
        else:
            # 传统流程需要初始化变量（如果传统流程被启用的话）
            logger.warning(f"⚠️ Task {task_id}: 智能路由未完成，但传统流程被注释")
            logger.warning(f"⚠️ Task {task_id}: 跳过引用解析，因为缺少必要的 literature_id")
            
            # 🔄 根据智能路由的错误类型返回相应的TaskResultType
            router_error_type = smart_router_result.get('error_type') if 'smart_router_result' in locals() else None
            
            if router_error_type == "url_not_found":
                result_type = TaskResultType.URL_NOT_FOUND
            elif router_error_type == "url_access_failed":
                result_type = TaskResultType.URL_ACCESS_FAILED
            else:
                result_type = TaskResultType.PARSING_FAILED
            
            logger.info(f"🔄 Task {task_id}: 返回错误类型 {result_type} (基于 {router_error_type})")
            return task_manager.complete_task(result_type, None)
        
        # 4. Fetch References (Critical Component) - 优先处理关键组件
        update_task_status("获取参考文献", progress=40)

        # Initialize references variable to avoid UnboundLocalError
        references = []
        references_source = "未知来源"

        # Check dependencies before proceeding
        deps_met = await dao.check_component_dependencies(literature_id, "references")
        if not deps_met:
            await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="references",
                status="waiting",
                stage="等待依赖完成",
                progress=0,
                dependencies_met=False,
                next_action="等待元数据获取完成",
            )
            logger.info("References fetch waiting for dependencies")
        else:
            await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="references",
                status="processing",
                stage="正在获取参考文献",
                progress=0,
                dependencies_met=True,
                next_action="尝试从外部API获取参考文献",
            )

            references_fetcher = ReferencesFetcher()
            references_result = references_fetcher.fetch_references_waterfall(
                identifiers=identifiers.model_dump(),
                pdf_content=None, # PDF content is handled later
            )

            # Handle result tuple safely
            if isinstance(references_result, tuple) and len(references_result) == 2:
                references, references_raw = references_result
                references_source = references_raw.get("source", "未知来源")
            else:
                references = references_result
                references_source = "未知来源"

            # Check if references fetch was actually successful with improved logic
            if references and len(references) > 0:
                overall_status = await dao.update_enhanced_component_status(
                    literature_id=literature_id,
                    component="references",
                    status="success",
                    stage="参考文献获取成功",
                    progress=100,
                    source=references_source or "未知来源",
                    next_action=None,
                )
                logger.info(
                    f"References fetch successful ({len(references)} refs) from {references_source}. Overall status: {overall_status}",
                )
                
                # 🎯 NEW: Citation Relationship Resolution
                logger.info(f"Task {task_id}: Starting citation relationship resolution")
                try:
                    from literature_parser_backend.worker.citation_resolver import CitationResolver
                    
                    # Initialize citation resolver
                    citation_resolver = CitationResolver(task_id=task_id)
                    await citation_resolver.initialize_with_dao(dao)
                    
                    # Resolve citations and create relationships
                    resolution_result = await citation_resolver.resolve_citations_for_literature(
                        citing_literature_lid=literature_id,
                        references=references
                    )
                    
                    stats = resolution_result["statistics"]
                    logger.info(f"Task {task_id}: Citation resolution completed - {stats['resolved_citations']} resolved, {stats['unresolved_references']} unresolved (rate: {stats['resolution_rate']:.2f})")
                    
                except Exception as e:
                    logger.error(f"Task {task_id}: Citation resolution failed: {e}")
                    # Don't fail the entire task for citation resolution errors
                    # This is a enhancement feature, not critical
            else:
                # Note: References failure is now critical
                error_info = {
                    "error_type": "ReferencesFetchError",
                    "error_message": "No references found or extraction failed",
                    "error_details": {
                        "attempted_sources": ["Semantic Scholar", "GROBID"],
                    },
                }
                overall_status = await dao.update_enhanced_component_status(
                    literature_id=literature_id,
                    component="references",
                    status="failed",
                    stage="参考文献获取失败",
                    progress=0,
                    error_info=error_info,
                    next_action="考虑手动输入参考文献",
                )
                logger.warning(f"References fetch failed. Overall status: {overall_status}")

        # 🚀 架构重构：完全跳过内容获取，专注核心功能测试
        # 6. 立即完成核心任务 - 保存元数据、引用、关系数据
        update_task_status("完成核心任务", progress=70)
        logger.info(f"Task {task_id}: ⚡ 跳过内容获取，直接完成核心数据处理")

        from datetime import datetime
        from ..models.literature import TaskInfoModel

        # Sync and get final overall status using smart status management (without content component)
        final_overall_status = await dao.sync_task_status(literature_id)
        logger.info(f"Core task synchronized status: {final_overall_status}")

        # Get current task_info from placeholder to preserve component statuses
        current_literature = await dao.find_by_lid(literature_id)
        if current_literature and current_literature.task_info:
            # Preserve the existing task_info with all component statuses
            task_info = current_literature.task_info
            # Update final status and completion time
            task_info.status = final_overall_status
            task_info.completed_at = datetime.now()
        else:
            # Fallback: create new task info (should not happen in normal flow)
            task_info = TaskInfoModel(
                task_id=task_id,
                status=final_overall_status,
                created_at=datetime.now(),
                completed_at=datetime.now(),
                error_message=None,
            )
            logger.warning(f"Could not find existing task_info for {literature_id}, created new one")

        # Ensure metadata is not None
        if metadata is None:
            from ..models.literature import MetadataModel

            metadata = MetadataModel(
                title="Unknown Title",
                authors=[],
                year=None,
                journal=None,
                abstract=None,
            )

        # Generate Literature ID (LID) from metadata
        lid_generator = LIDGenerator()
        generated_lid = lid_generator.generate_lid(metadata)
        
        # 🚀 创建文献对象 - 使用空的ContentModel，PDF内容将在后台处理
        from ..models.literature import ContentModel
        literature = LiteratureModel(
            user_id=None,  # Optional field for user association
            lid=generated_lid,  # Add the generated LID
            task_info=task_info,
            identifiers=identifiers,
            metadata=metadata,
            content=ContentModel(),  # 空的ContentModel，PDF将在后台异步填充
            references=references,
        )

        await dao.finalize_literature(literature_id, literature)
        logger.info(f"Task {task_id}: ✅ 核心文献数据已保存 (LID: {literature.lid})")
        
        # Record alias mappings for the newly created literature
        task_manager.update_task_progress("记录别名映射", 85, literature_id)
        await _record_alias_mappings(literature, source, dao, task_id)
        
        # 🆕 检查并升级匹配的未解析节点
        task_manager.update_task_progress("升级未解析节点", 90, literature_id)
        await _upgrade_matching_unresolved_nodes(literature, dao, task_id)
        
        # 🎯 先返回核心任务完成状态，让用户立即看到结果
        task_manager.update_task_progress("核心任务完成", 95, literature_id)
        logger.info(f"Task {task_id}: ✅ 核心任务已完成，用户可查看元数据和引用关系")
        
        # 🚫 完全跳过内容获取 - 专注测试核心功能
        logger.info(f"Task {task_id}: 🚫 内容获取已禁用，专注核心功能测试")
        
        task_manager.update_task_progress("处理完成", 100, literature_id)
        
        # 🛡️ 检查是否是解析失败的文献，如果是则返回特殊状态
        is_parsing_failed = False
        if metadata and metadata.title:
            failed_title_indicators = [
                "Unknown Title",
                "Processing...",
                "Extracting...",
                "Loading...",
                "Error:",
                "N/A",
                "Parsing Failed"
            ]
            is_parsing_failed = any(indicator in metadata.title for indicator in failed_title_indicators)
        
        # 🔧 智能路由和传统流程的统一返回
        if 'smart_router_completed' in locals() and smart_router_completed:
            # 智能路由完成，合并结果
            # 🎯 基于实际组件状态判断结果类型，而不是标题检查
            if final_overall_status == "completed":
                result_type = TaskResultType.CREATED
            elif final_overall_status in ["partial_completed", "processing"]:
                result_type = TaskResultType.CREATED  # 部分成功也算创建成功
            else:  # failed
                result_type = TaskResultType.PARSING_FAILED
            
            logger.info(f"✅ Task {task_id}: 智能路由+引用解析完成 (状态: {final_overall_status} -> {result_type})")
            final_result = task_manager.complete_task(result_type, literature_id)
            
            # 添加智能路由的额外信息
            final_result.update({
                'route_used': smart_router_result.get('route_used'),
                'processor_used': smart_router_result.get('processor_used'),
                'smart_router_time': smart_router_result.get('execution_time'),
                'references_count': len(references) if 'references' in locals() else 0,
                'mode': 'smart_router_with_references',
                'is_parsing_failed': is_parsing_failed
            })
            return final_result
        else:
            # 纯传统流程
            # 🎯 基于实际组件状态判断结果类型，而不是标题检查
            if final_overall_status == "completed":
                result_type = TaskResultType.CREATED
            elif final_overall_status in ["partial_completed", "processing"]:
                result_type = TaskResultType.CREATED  # 部分成功也算创建成功
            else:  # failed
                result_type = TaskResultType.PARSING_FAILED
            
            logger.info(f"✅ Task {task_id}: 传统流程完成 (状态: {final_overall_status} -> {result_type})")
            # Return LID instead of MongoDB ObjectId for API consistency
            final_result = task_manager.complete_task(result_type, literature.lid or literature_id)
            final_result['is_parsing_failed'] = (result_type == TaskResultType.PARSING_FAILED)
            return final_result


    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        if 'task_manager' in locals():
            task_manager.update_task_progress("处理失败", 100, locals().get('literature_id'))
            return task_manager.fail_task(str(e), locals().get('literature_id'))
        else:
            # 如果task_manager还没创建，直接抛出异常
            raise
    finally:
        # Always close the task connection
        if client:
            await close_task_connection(client)


@celery_app.task(bind=True, name="process_literature_task")
def process_literature_task(self: Task, source: Dict[str, Any]) -> Dict[str, Any]:
    """Celery task entry point for literature processing."""
    try:
        # 🔍 DEBUG: Check what data Worker receives from API
        logger.info("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢")
        logger.info(f"📋 [WORKER] 🚀【任务日志开始】Task {self.request.id} received source data:")
        logger.info(f"📋 [WORKER] Source keys: {list(source.keys()) if source else 'None'}")
        logger.info(f"📋 [WORKER] Source data: {source}")
        logger.info("🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢")
        
        # Check specific identifiers field
        if 'identifiers' in source:
            logger.info(f"📋 [WORKER] Identifiers field: {source['identifiers']}")
        else:
            logger.info(f"📋 [WORKER] ❌ No 'identifiers' field in source data!")
            
        # Important: run the async function and get the dictionary result
        result_dict = asyncio.run(_process_literature_async(self.request.id, source))
        return result_dict
    except Exception as e:
        # 导入自定义异常类型和结果类型
        from .execution.exceptions import URLNotFoundException, URLAccessFailedException, ParsingFailedException
        from ..models.task import TaskResultType
        
        logger.error(f"Task {self.request.id} failed: {e}", exc_info=True)
        
        # 根据异常类型返回不同的结果类型
        if isinstance(e, URLNotFoundException):
            return {
                "result_type": TaskResultType.URL_NOT_FOUND.value,
                "error_message": str(e),
                "literature_id": None
            }
        elif isinstance(e, URLAccessFailedException):
            return {
                "result_type": TaskResultType.URL_ACCESS_FAILED.value,
                "error_message": str(e),
                "literature_id": None
            }
        elif isinstance(e, ParsingFailedException):
            return {
                "result_type": TaskResultType.PARSING_FAILED.value,
                "error_message": str(e),
                "literature_id": None
            }
        else:
            # 其他未知异常，标记为任务失败
            update_task_status("处理失败", progress=100)
            self.update_state(
                state="FAILURE",
                meta={"error": str(e), "exc_type": type(e).__name__},
            )
            return {
                "status": "FAILURE",
                "error": str(e),
                "exc_type": type(e).__name__,
            }
