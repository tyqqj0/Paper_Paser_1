"""
Celery tasks for literature processing.

This module contains the core literature processing task that implements
the intelligent hybrid workflow for gathering metadata and references.
"""

import hashlib
import logging
import asyncio
from typing import Any, Dict, Optional, Tuple

from celery import Task, current_task

from ..db.dao import LiteratureDAO
from ..db.mongodb import create_task_connection, close_task_connection
from ..models.literature import (
    IdentifiersModel,
    LiteratureCreateRequestDTO,
    LiteratureModel,
    MetadataModel,
)
from ..services import GrobidClient, SemanticScholarClient
from ..settings import Settings
from .celery_app import celery_app
from .content_fetcher import ContentFetcher
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
    # 1. Direct identifier check (DOI, ArXiv ID)
    if identifiers.doi:
        if literature := await dao.find_by_doi(identifiers.doi):
            return str(literature.id), None, None
    if identifiers.arxiv_id:
        if literature := await dao.find_by_arxiv_id(identifiers.arxiv_id):
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
                
                # Check by fingerprint
                if literature := await dao.find_by_fingerprint(fingerprint):
                    return str(literature.id), None, pdf_content
                
                # Try to extract title with GROBID for title-based deduplication
                try:
                    grobid_client = GrobidClient()
                    parsed_data = grobid_client.process_header_only(pdf_content)
                    prefetched_metadata = convert_grobid_to_metadata(parsed_data)
                    
                    if prefetched_metadata and prefetched_metadata.title != "Unknown Title":
                        if literature := await dao.find_by_title(prefetched_metadata.title):
                            return str(literature.id), prefetched_metadata, pdf_content
                except Exception as e:
                    logger.warning(f"GROBID prefetch failed: {e}")
        except Exception as e:
            logger.warning(f"PDF download/processing failed: {e}")
    
    return None, prefetched_metadata, pdf_content

async def _process_literature_async(task_id: str, source: Dict[str, Any]) -> Dict[str, Any]:
    """Asynchronous core logic for processing literature."""
    # Create dedicated database connection for this task
    client = None
    try:
        client, database = await create_task_connection()
        
        update_task_status("任务开始", progress=0)
        dao = LiteratureDAO.create_from_task_connection(database)
        
        # 1. Identifier Extraction & Deduplication
        identifiers, _ = extract_authoritative_identifiers(source)
        existing_id, prefetched_meta, pdf_content = await _deduplicate_literature(
            identifiers, source, dao, task_id
        )
        
        if existing_id:
            update_task_status("文献已存在", progress=100)
            return {"status": "SUCCESS_DUPLICATE", "literature_id": existing_id}

        # 2. Create Placeholder and update task metadata
        literature_id = await dao.create_placeholder(task_id, identifiers)
        current_task.update_state(meta={'literature_id': literature_id})
        
        update_task_status("获取元数据", progress=20)
        await dao.update_component_status(literature_id, "metadata", "processing")
        
        # 3. Fetch Metadata
        metadata_fetcher = MetadataFetcher()
        metadata, _ = metadata_fetcher.fetch_metadata_waterfall(
            identifiers=identifiers.model_dump(),
            source_data=source,
            pre_fetched_metadata=prefetched_meta,
            pdf_content=pdf_content, # Pass PDF content for GROBID fallback
        )
        await dao.update_component_status(literature_id, "metadata", "success")

        # 4. Fetch Content
        if not pdf_content:
            content_fetcher = ContentFetcher()
            content_model, _ = content_fetcher.fetch_content_waterfall(
                doi=identifiers.doi,
                arxiv_id=identifiers.arxiv_id,
                user_pdf_url=source.get("pdf_url"),
            )
        else:
            # If PDF was fetched during deduplication, build ContentModel
            from ..models.literature import ContentModel
            content_model = ContentModel(
                pdf_url=source.get("pdf_url"),
                sources_tried=[f"user_pdf_url: {source.get('pdf_url')}"]
            )
            if prefetched_meta: # Fill in parsed text from pre-fetch
                 content_model.parsed_fulltext = {"title": prefetched_meta.title}
            await dao.update_component_status(literature_id, "content", "success")

        # 5. Fetch References
        references_fetcher = ReferencesFetcher()
        references, _ = references_fetcher.fetch_references_waterfall(
            identifiers=identifiers.model_dump(), pdf_content=pdf_content
        )
        await dao.update_component_status(literature_id, "references", "success")

        # 6. Finalize
        from ..models.literature import TaskInfoModel
        from datetime import datetime

        task_info = TaskInfoModel(
            task_id=task_id,
            status="completed",
            created_at=datetime.now(),
            completed_at=datetime.now(),
        )

        literature = LiteratureModel(
            task_info=task_info,
            identifiers=identifiers,
            metadata=metadata,
            content=content_model,
            references=references,
        )

        final_literature_model = await dao.finalize_literature(literature_id, literature)
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
            state='FAILURE',
            meta={'error': str(e), 'exc_type': type(e).__name__}
        )
        # The result returned here will be available in the task's result store
        return {
            "status": "FAILURE",
            "error": str(e),
            "exc_type": type(e).__name__,
        }
