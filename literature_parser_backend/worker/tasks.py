"""
Celery tasks for literature processing.

This module contains the core literature processing task that implements
the intelligent hybrid workflow for gathering metadata and references.
"""

import asyncio
import hashlib
import logging
from typing import Any, Dict, Optional, Tuple

from celery import Task, current_task

from ..db.dao import LiteratureDAO
from ..db.mongodb import close_task_connection, create_task_connection
from ..models.literature import (
    IdentifiersModel,
    LiteratureModel,
    MetadataModel,
)
from ..services import GrobidClient
from .celery_app import celery_app
from .content_fetcher import ContentFetcher
from .deduplication import WaterfallDeduplicator
from .metadata_fetcher import MetadataFetcher
from .references_fetcher import ReferencesFetcher
from .utils import (
    convert_grobid_to_metadata,
    extract_authoritative_identifiers,
    update_task_status,
)

logger = logging.getLogger(__name__)


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


async def _process_literature_async(
    task_id: str,
    source: Dict[str, Any],
) -> Dict[str, Any]:
    """Asynchronous core logic for processing literature."""
    # Create dedicated database connection for this task
    client = None
    try:
        client, database = await create_task_connection()

        update_task_status("任务开始", progress=0)
        dao = LiteratureDAO.create_from_task_connection(database)

        # 1. Enhanced Waterfall Deduplication
        deduplicator = WaterfallDeduplicator(dao, task_id)
        existing_id, prefetched_meta, pdf_content = (
            await deduplicator.deduplicate_literature(source)
        )

        # Extract identifiers for downstream processing
        identifiers, _ = extract_authoritative_identifiers(source)

        if existing_id:
            update_task_status("文献已存在", progress=100)
            return {"status": "SUCCESS_DUPLICATE", "literature_id": existing_id}

        # 2. Create Placeholder and update task metadata
        literature_id = await dao.create_placeholder(task_id, identifiers)
        current_task.update_state(meta={"literature_id": literature_id})

        update_task_status("获取元数据", progress=20)
        await dao.update_enhanced_component_status(
            literature_id=literature_id,
            component="metadata",
            status="processing",
            stage="正在获取元数据",
            progress=0,
            next_action="尝试从外部API获取元数据",
        )

        # 3. Fetch Metadata (Critical Component)
        metadata_fetcher = MetadataFetcher()
        metadata_result = metadata_fetcher.fetch_metadata_waterfall(
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

        # Check if metadata fetch was actually successful and update with enhanced method
        if metadata and metadata.title and metadata.title != "Unknown Title":
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
                f"Metadata fetch successful from {metadata_source}. Overall status: {overall_status}",
            )
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

        # 4. Fetch Content (Optional Component)
        update_task_status("获取内容", progress=40)
        await dao.update_enhanced_component_status(
            literature_id=literature_id,
            component="content",
            status="processing",
            stage="正在获取内容",
            progress=0,
            next_action="尝试下载PDF文件",
        )

        if not pdf_content:
            content_fetcher = ContentFetcher()
            content_result = content_fetcher.fetch_content_waterfall(
                doi=identifiers.doi,
                arxiv_id=identifiers.arxiv_id,
                user_pdf_url=source.get("pdf_url"),
            )

            # Handle result tuple safely
            if isinstance(content_result, tuple) and len(content_result) == 2:
                content_model, content_raw = content_result
                content_source = content_raw.get("source", "未知来源")
            else:
                content_model = content_result
                content_source = "未知来源"
        else:
            # If PDF was fetched during deduplication, build ContentModel
            from ..models.literature import ContentModel

            content_model = ContentModel(
                pdf_url=source.get("pdf_url"),
                sources_tried=[f"user_pdf_url: {source.get('pdf_url')}"],
            )
            if prefetched_meta:  # Fill in parsed text from pre-fetch
                content_model.parsed_fulltext = {"title": prefetched_meta.title}
            content_source = "deduplication_prefetch"

        # Check if content fetch was actually successful with improved logic
        if content_model and (content_model.pdf_url or content_model.parsed_fulltext):
            # Additional check: if we have PDF but GROBID failed, it's still a partial failure
            grobid_failed = (
                content_model.pdf_url
                and hasattr(content_model, "grobid_processing_info")
                and content_model.grobid_processing_info
                and content_model.grobid_processing_info.get("status") == "error"
            )

            if grobid_failed and not content_model.parsed_fulltext:
                # We have PDF but GROBID failed and no parsed text - this is a failure
                error_info = {
                    "error_type": "ContentParsingError",
                    "error_message": "PDF downloaded but GROBID parsing failed",
                    "error_details": {
                        "pdf_downloaded": True,
                        "grobid_status": "failed",
                    },
                }
                overall_status = await dao.update_enhanced_component_status(
                    literature_id=literature_id,
                    component="content",
                    status="failed",
                    stage="内容解析失败",
                    progress=0,
                    error_info=error_info,
                    next_action="考虑手动上传解析后的内容",
                )
                logger.warning(
                    f"Content fetch failed - PDF downloaded but parsing failed. Overall status: {overall_status}",
                )
            else:
                overall_status = await dao.update_enhanced_component_status(
                    literature_id=literature_id,
                    component="content",
                    status="success",
                    stage="内容获取成功",
                    progress=100,
                    source=content_source or "未知来源",
                    next_action=None,
                )
                logger.info(
                    f"Content fetch successful from {content_source}. Overall status: {overall_status}",
                )
        else:
            error_info = {
                "error_type": "ContentFetchError",
                "error_message": "Failed to fetch PDF content or parsed text",
                "error_details": {
                    "attempted_sources": ["user_pdf_url", "arxiv", "unpaywall"],
                },
            }
            overall_status = await dao.update_enhanced_component_status(
                literature_id=literature_id,
                component="content",
                status="failed",
                stage="内容获取失败",
                progress=0,
                error_info=error_info,
                next_action="可尝试手动上传PDF文件",
            )
            logger.warning(f"Content fetch failed. Overall status: {overall_status}")

        # 5. Fetch References (Critical Component)
        update_task_status("获取参考文献", progress=60)

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
                next_action="等待元数据或内容获取完成",
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
                logger.warning(
                    f"References fetch failed (now critical). Overall status: {overall_status}",
                )

        # 6. Finalize
        update_task_status("完成任务", progress=80)

        from datetime import datetime

        from ..models.literature import TaskInfoModel

        # Sync and get final overall status using smart status management
        final_overall_status = await dao.sync_task_status(literature_id)
        logger.info(f"Final synchronized task status: {final_overall_status}")

        # Create task info with the calculated status
        task_info = TaskInfoModel(
            task_id=task_id,
            status=final_overall_status,
            created_at=datetime.now(),
            completed_at=datetime.now(),
            error_message=None,  # Will be preserved from component updates
        )

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

        literature = LiteratureModel(
            user_id=None,  # Optional field for user association
            task_info=task_info,
            identifiers=identifiers,
            metadata=metadata,
            content=content_model,
            references=references,
        )

        await dao.finalize_literature(literature_id, literature)
        update_task_status("处理完成", progress=100)
        return {"status": "SUCCESS_CREATED", "literature_id": literature_id}

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        update_task_status("处理失败", progress=100)
        raise
    finally:
        # Always close the task connection
        if client:
            await close_task_connection(client)


# ===============================================
# Celery Task Entry Point
# ===============================================


@celery_app.task(bind=True, name="process_literature_task")
def process_literature_task(self: Task, source: Dict[str, Any]) -> Dict[str, Any]:
    """Celery task entry point for literature processing."""
    try:
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
