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
    if not metadata.title or metadata.title in ["Unknown Title", "Processing..."]:
        missing_fields.append("title")
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
    existing_lit = None
    # 1. Check by DOI first (most reliable)
    if identifiers and identifiers.doi:
        existing_lit = await dao.find_by_doi(identifiers.doi)

    # 2. If no DOI match, check by title similarity
    if not existing_lit and metadata and metadata.title:
        # Use fuzzy search to get candidates, then a more precise similarity check
        candidates = await dao.find_by_title_fuzzy(metadata.title, limit=5)
        for cand_lit in candidates:
            if cand_lit.metadata and cand_lit.metadata.title:
                # Use a standard, balanced matching mode
                if TitleMatchingUtils.is_acceptable_match(
                    cand_lit.metadata.title, metadata.title, mode=MatchingMode.STANDARD
                ):
                    # As an extra precaution, check year difference for non-DOI matches
                    if metadata.year and cand_lit.metadata.year:
                        try:
                            year_diff = abs(int(metadata.year) - int(cand_lit.metadata.year))
                            if year_diff > 2:  # Allow up to 2 years difference
                                continue  # Likely a different version, not a duplicate
                        except (ValueError, TypeError):
                            pass  # Ignore if year is not a valid integer
                    existing_lit = cand_lit
                    break  # Found a match

    # 3. If a duplicate is found, handle it
    if not existing_lit and metadata and metadata.title:
        logger.info(f"Task {task_id}: Starting secondary deduplication for title: '{metadata.title}'")
        
        # 2a. Check for exact match after normalization
        # This is the most reliable way to find duplicates
        candidates = await dao.find_by_title_fuzzy(metadata.title, limit=10)
        logger.info(f"Task {task_id}: Found {len(candidates)} potential candidates for title match.")

        for i, cand_lit in enumerate(candidates):
            if cand_lit.metadata and cand_lit.metadata.title:
                norm_new = TitleMatchingUtils.normalize_title(metadata.title)
                norm_cand = TitleMatchingUtils.normalize_title(cand_lit.metadata.title)
                exact_match_result = TitleMatchingUtils.is_exact_match(cand_lit.metadata.title, metadata.title)

                logger.info(f"Task {task_id}: Candidate {i+1}/{len(candidates)} LID: {cand_lit.lid}")
                logger.info(f"  - New Title (raw): '{metadata.title}'")
                logger.info(f"  - Cand. Title (raw): '{cand_lit.metadata.title}'")
                logger.info(f"  - New Title (norm): '{norm_new}'")
                logger.info(f"  - Cand. Title (norm): '{norm_cand}'")
                logger.info(f"  - Exact Match? -> {exact_match_result}")

                if exact_match_result:
                    existing_lit = cand_lit
                    logger.info(f"Task {task_id}: Found duplicate by exact title match: {existing_lit.lid}")
                    break  # Found exact match

    # 2b. If no exact match, fall back to similarity-based matching
    if not existing_lit and metadata and metadata.title:
        logger.info(f"Task {task_id}: No exact match found, proceeding to similarity-based matching.")
        if 'candidates' not in locals(): # Reuse candidates if already fetched
             candidates = await dao.find_by_title_fuzzy(metadata.title, limit=5)
        
        for i, cand_lit in enumerate(candidates):
            if cand_lit.metadata and cand_lit.metadata.title:
                similarity = TitleMatchingUtils.calculate_similarity_by_mode(cand_lit.metadata.title, metadata.title, mode=MatchingMode.STANDARD)
                is_match = similarity >= 0.8 # Using default threshold for STANDARD mode

                logger.info(f"Task {task_id}: Similarity Candidate {i+1}/{len(candidates)} LID: {cand_lit.lid}")
                logger.info(f"  - Similarity Score: {similarity:.4f} (Mode: STANDARD, Threshold: 0.8)")
                logger.info(f"  - Acceptable Match? -> {is_match}")

                if is_match:
                    # As an extra precaution, check year difference for non-DOI matches
                    if metadata.year and cand_lit.metadata.year:
                        try:
                            year_diff = abs(int(metadata.year) - int(cand_lit.metadata.year))
                            if year_diff > 2:  # Allow up to 2 years difference
                                logger.info(f"  - Year diff {year_diff} > 2, rejecting match.")
                                continue  # Likely a different version, not a duplicate
                        except (ValueError, TypeError):
                            pass  # Ignore if year is not a valid integer
                    existing_lit = cand_lit
                    logger.info(f"Task {task_id}: Found duplicate by similarity match: {existing_lit.lid}")
                    break  # Found a match

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

        # 1. Enhanced Waterfall Deduplication
        logger.info(f"Task {task_id}: About to start deduplication with source: {source}")
        deduplicator = WaterfallDeduplicator(dao, task_id)
        existing_id, prefetched_meta, pdf_content = (
            await deduplicator.deduplicate_literature(source)
        )
        logger.info(f"Task {task_id}: Deduplication completed. Existing ID: {existing_id}")

        # Extract identifiers for downstream processing
        logger.info(f"Task {task_id}: 🔍 [DEBUG] About to extract identifiers from source")
        logger.info(f"Task {task_id}: 🔍 [DEBUG] Source keys: {list(source.keys())}")
        logger.info(f"Task {task_id}: 🔍 [DEBUG] Source data: {source}")
        
        try:
            identifiers, primary_type, url_validation_info = extract_authoritative_identifiers(source)
            
            logger.info(f"Task {task_id}: ✅ Identifier extraction completed")
            logger.info(f"Task {task_id}: 🔍 [DEBUG] Extracted DOI: {identifiers.doi}")
            logger.info(f"Task {task_id}: 🔍 [DEBUG] Extracted ArXiv ID: {identifiers.arxiv_id}")
            logger.info(f"Task {task_id}: 🔍 [DEBUG] Primary type: {primary_type}")

            # 如果有URL验证信息，存储到任务状态中并添加到source_data
            if url_validation_info:
                task_manager.set_url_validation_info(url_validation_info)
                # 🆕 将URL映射结果添加到source中，供元数据获取器使用
                source.update(url_validation_info)

        except ValueError as e:
            # URL验证失败，创建错误信息并终止任务
            if "URL验证失败" in str(e):
                logger.error(f"任务 {task_id} URL验证失败: {e}")

                # 创建URL验证失败的错误信息
                from ..models.task import TaskErrorInfo
                from datetime import datetime
                error_info = TaskErrorInfo(
                    error_type="URLValidationError",
                    error_message=str(e),
                    error_category="url_validation",
                    url_validation_details={
                        "original_url": source.get("url"),
                        "error_type": "url_not_accessible",
                        "validation_time": str(datetime.now()),
                    }
                )

                # 更新任务状态为失败
                task_manager.fail_task_with_url_validation_error(error_info, source.get("url"))

                # 直接返回URL验证失败的结果，不抛出异常（避免Celery序列化问题）
                return {
                    "status": TaskExecutionStatus.FAILED,
                    "error_message": str(e),
                    "error_category": "url_validation",
                    "url_validation_status": "failed",
                    "url_validation_error": str(e),
                    "original_url": source.get("url"),
                }
            else:
                # 其他类型的错误，继续原有处理逻辑
                raise e

        if existing_id:
            task_manager.update_task_progress("文献已存在，检查新别名", 90, existing_id)
            
            # Check and record any new alias mappings for existing literature
            try:
                existing_literature = await dao.get_literature_by_id(existing_id)
                if existing_literature and existing_literature.lid:
                    # Create alias DAO
                    alias_dao = AliasDAO.create_from_task_connection(database)
                    
                    # Extract aliases from current source data
                    source_aliases = extract_aliases_from_source(source)
                    
                    # Check which aliases are new
                    new_mappings = {}
                    for alias_type, alias_value in source_aliases.items():
                        # Check if this alias already exists
                        existing_lid = await alias_dao._lookup_single_alias(alias_type, alias_value)
                        if not existing_lid:
                            # This is a new alias for the existing literature
                            new_mappings[alias_type] = alias_value
                    
                    if new_mappings:
                        # Create new alias mappings
                        created_ids = await alias_dao.batch_create_mappings(
                            lid=existing_literature.lid,
                            mappings=new_mappings,
                            confidence=1.0,
                            metadata={
                                "source": "deduplication_discovery",
                                "task_id": task_id,
                                "created_from": "new_identifier_mapping"
                            }
                        )
                        
                        logger.info(
                            f"Task {task_id}: Created {len(created_ids)} new alias mappings for existing LID {existing_literature.lid}: {list(new_mappings.keys())}"
                        )
                    else:
                        logger.info(f"Task {task_id}: No new aliases found for existing literature {existing_literature.lid}")
                        
            except Exception as e:
                # Don't fail the task if alias recording fails
                logger.error(f"Task {task_id}: Failed to record new aliases for existing literature {existing_id}: {e}")
            
            task_manager.update_task_progress("文献已存在", 100, existing_id)
            # For duplicate, also return LID if available
            existing_literature = await dao.get_literature_by_id(existing_id)
            
            # If existing literature has no LID (old literature), generate one
            if existing_literature and not existing_literature.lid and existing_literature.metadata:
                lid_generator = LIDGenerator()
                generated_lid = lid_generator.generate_lid(existing_literature.metadata)
                
                # Update the literature with the new LID
                existing_literature.lid = generated_lid
                await dao.finalize_literature(existing_id, existing_literature)
                
                logger.info(f"Task {task_id}: Generated LID {generated_lid} for existing literature {existing_id}")
                final_id = generated_lid
            else:
                final_id = existing_literature.lid if existing_literature and existing_literature.lid else existing_id
                
            return task_manager.complete_task(TaskResultType.DUPLICATE, final_id)

        # 2. Create Placeholder and update task metadata
        literature_id = await dao.create_placeholder(task_id, identifiers)
        task_manager.update_task_progress("创建文献占位符", 10, literature_id)

        # 3. 开始获取元数据
        task_manager.update_task_progress("获取元数据", 20, literature_id)
        await dao.update_enhanced_component_status(
            literature_id=literature_id,
            component="metadata",
            status="processing",
            stage="正在获取元数据",
            progress=0,
            next_action="尝试从外部API获取元数据",
        )

        # 获取元数据（关键组件）
        metadata_fetcher = MetadataFetcher()
        metadata_result = await metadata_fetcher.fetch_metadata_waterfall(
            identifiers=identifiers.model_dump(),
            source_data=source,
            pre_fetched_metadata=prefetched_meta,
            pdf_content=pdf_content,  # Pass PDF content for GROBID fallback
        )

        # Handle result tuple safely
        if isinstance(metadata_result, tuple) and len(metadata_result) == 2:
            metadata, metadata_raw = metadata_result
            metadata_source = metadata_raw.get("source", "未知来源")
        else:
            metadata = metadata_result
            metadata_source = "未知来源"

        # 检查元数据获取是否成功并更新状态 - 使用严格的质量评估
        metadata_quality_check = _evaluate_metadata_quality(metadata, metadata_source)

        # NEW: Secondary deduplication after getting metadata
        if metadata and (metadata_quality_check["is_high_quality"] or metadata_quality_check["is_partial"]):
            existing_lid_after_fetch = await _check_and_handle_post_metadata_duplicate(
                dao=dao,
                identifiers=identifiers,
                metadata=metadata,
                source_data=source,
                placeholder_lid=literature_id,
                task_id=task_id,
            )
            if existing_lid_after_fetch:
                logger.info(f"Task {task_id}: Concluding task as DUPLICATE after secondary check.")
                return task_manager.complete_task(TaskResultType.DUPLICATE, existing_lid_after_fetch)
        
        if metadata_quality_check["is_high_quality"]:
            overall_status = await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="metadata",
                status="success",
                stage="元数据获取成功",
                progress=100,
                source=metadata_source or "未知来源",
                next_action=None,
            )
            logger.info(
                f"Metadata fetch successful from {metadata_source}. Quality: {metadata_quality_check['quality_score']}/100. Overall status: {overall_status}",
            )
            
            # 🆕 重要修复：更新identifiers以便引用获取使用
            # 如果元数据中包含新的标识符信息，更新到identifiers变量中
            if metadata and hasattr(metadata, 'doi') and metadata.doi and not identifiers.doi:
                logger.info(f"Task {task_id}: 🔄 更新DOI到identifiers: {metadata.doi}")
                identifiers.doi = metadata.doi
            
            # 检查是否有ArXiv ID（如果元数据中包含external IDs）
            if hasattr(metadata, 'external_ids') and metadata.external_ids:
                if 'ArXiv' in metadata.external_ids and not identifiers.arxiv_id:
                    arxiv_id = metadata.external_ids['ArXiv']
                    logger.info(f"Task {task_id}: 🔄 更新ArXiv ID到identifiers: {arxiv_id}")
                    identifiers.arxiv_id = arxiv_id
            
            logger.info(f"Task {task_id}: 🔍 [DEBUG] 更新后的标识符: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
        elif metadata_quality_check["is_partial"]:
            # 部分成功：有基本信息但缺少重要字段
            overall_status = await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="metadata",
                status="partial",
                stage="元数据部分获取",
                progress=metadata_quality_check["quality_score"],
                source=metadata_source or "未知来源",
                error_info={
                    "error_type": "PartialMetadataError",
                    "error_message": f"元数据不完整: {', '.join(metadata_quality_check['missing_fields'])}",
                    "error_details": {
                        "missing_fields": metadata_quality_check["missing_fields"],
                        "quality_score": metadata_quality_check["quality_score"],
                        "attempted_sources": ["CrossRef", "Semantic Scholar", "GROBID"]
                    }
                },
                next_action="尝试其他数据源获取完整元数据",
            )
            logger.warning(
                f"Metadata partially successful from {metadata_source}. Missing: {metadata_quality_check['missing_fields']}. Overall status: {overall_status}",
            )
            
            # 🆕 即使是部分成功，也要更新标识符信息
            if metadata and hasattr(metadata, 'doi') and metadata.doi and not identifiers.doi:
                logger.info(f"Task {task_id}: 🔄 [部分成功] 更新DOI到identifiers: {metadata.doi}")
                identifiers.doi = metadata.doi
            
            if hasattr(metadata, 'external_ids') and metadata.external_ids:
                if 'ArXiv' in metadata.external_ids and not identifiers.arxiv_id:
                    arxiv_id = metadata.external_ids['ArXiv']
                    logger.info(f"Task {task_id}: 🔄 [部分成功] 更新ArXiv ID到identifiers: {arxiv_id}")
                    identifiers.arxiv_id = arxiv_id
            
            logger.info(f"Task {task_id}: 🔍 [DEBUG] [部分成功] 更新后的标识符: DOI={identifiers.doi}, ArXiv={identifiers.arxiv_id}")
        else:
            error_info = {
                "error_type": "MetadataFetchError",
                "error_message": "Failed to fetch valid metadata",
                "error_details": {
                    "attempted_sources": ["CrossRef", "Semantic Scholar", "GROBID"],
                },
            }
            overall_status = await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="metadata",
                status="failed",
                stage="元数据获取失败",
                progress=0,
                error_info=error_info,
                next_action="考虑手动输入元数据",
            )
            logger.warning(f"Metadata fetch failed. Overall status: {overall_status}")

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
                pdf_content=pdf_content,
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
        # Return LID instead of MongoDB ObjectId for API consistency
        return task_manager.complete_task(TaskResultType.CREATED, literature.lid or literature_id)

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
        logger.info(f"📋 [WORKER] Task {self.request.id} received source data:")
        logger.info(f"📋 [WORKER] Source keys: {list(source.keys()) if source else 'None'}")
        logger.info(f"📋 [WORKER] Source data: {source}")
        
        # Check specific identifiers field
        if 'identifiers' in source:
            logger.info(f"📋 [WORKER] Identifiers field: {source['identifiers']}")
        else:
            logger.info(f"📋 [WORKER] ❌ No 'identifiers' field in source data!")
            
        # Important: run the async function and get the dictionary result
        result_dict = asyncio.run(_process_literature_async(self.request.id, source))
        return result_dict
    except Exception as e:
        logger.error(f"Task {self.request.id} failed: {e}", exc_info=True)
        # Directly update the task state to FAILURE with error details
        update_task_status("处理失败", progress=100)
        self.update_state(
            state="FAILURE",
            meta={"error": str(e), "exc_type": type(e).__name__},
        )
        # The result returned here will be available in the task's result store
        return {
            "status": "FAILURE",
            "error": str(e),
            "exc_type": type(e).__name__,
        }
