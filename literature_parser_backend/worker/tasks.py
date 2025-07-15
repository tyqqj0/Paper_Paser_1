"""
Celery tasks for literature processing.

This module contains the core literature processing task that implements
the intelligent hybrid workflow for gathering metadata and references.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pymongo
from celery import current_task

from ..models import (
    AuthorModel,
    ContentModel,
    IdentifiersModel,
    LiteratureModel,
    MetadataModel,
    ReferenceModel,
    TaskInfoModel,
)
from ..settings import Settings
from .celery_app import celery_app

logger = logging.getLogger(__name__)


def _save_literature_sync(literature: LiteratureModel, settings: Settings) -> str:
    """
    Save literature to MongoDB using synchronous operations for Celery compatibility.

    Args:
        literature: Literature data to save
        settings: Application settings

    Returns:
        str: The created literature ID
    """
    mongo_url = f"mongodb://{settings.db_user}:{settings.db_pass}@{settings.db_host}:{settings.db_port}/admin"
    client = pymongo.MongoClient(mongo_url)
    db = client[settings.db_base]
    collection = db.literatures

    try:
        doc_data = literature.model_dump()
        now = datetime.now()
        doc_data["created_at"] = now
        doc_data["updated_at"] = now
        result = collection.insert_one(doc_data)
        logger.info(f"Literature saved to MongoDB with ID: {result.inserted_id}")
        return str(result.inserted_id)
    finally:
        client.close()


settings = Settings()


def update_task_status(stage: str, progress: int = None, details: str = None):
    """Update the current task's status with stage information."""
    if current_task:
        meta = {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        }
        if progress is not None:
            meta["progress"] = progress
        if details:
            meta["details"] = details

        current_task.update_state(state="PROCESSING", meta=meta)
        logger.info(
            f"Task {current_task.request.id}: {stage} - {details or 'In progress'}",
        )


def extract_authoritative_identifiers(
    source: Dict[str, Any],
) -> Tuple[IdentifiersModel, str]:
    """
    Extract authoritative identifiers from source data.
    Priority: DOI > ArXiv ID > Other academic IDs > Generated fingerprint
    """
    identifiers = IdentifiersModel()
    primary_type = None
    doi_pattern = r"10\.\d{4,}/[^\s]+"

    if source.get("url"):
        url = source["url"]
        if "doi.org" in url:
            doi_match = re.search(doi_pattern, url)
            if doi_match:
                identifiers.doi = doi_match.group()
                primary_type = "doi"
        elif "arxiv.org" in url:
            arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?]+)", url)
            if arxiv_match:
                identifiers.arxiv_id = arxiv_match.group(1)
                if not primary_type:
                    primary_type = "arxiv"

    if source.get("doi") and not identifiers.doi:
        identifiers.doi = source["doi"]
        primary_type = "doi"

    if source.get("arxiv_id") and not identifiers.arxiv_id:
        identifiers.arxiv_id = source["arxiv_id"]
        if not primary_type:
            primary_type = "arxiv"

    if not identifiers.doi and not identifiers.arxiv_id:
        title = source.get("title", "")
        authors = source.get("authors", "")
        year = source.get("year", "")
        content = f"{title}|{authors}|{year}".lower().strip()
        if content and content != "||":
            identifiers.fingerprint = hashlib.md5(content.encode()).hexdigest()[:16]
            primary_type = "fingerprint"

    return identifiers, primary_type or "fingerprint"


def _process_literature(task_id: str, source: Dict[str, Any]) -> str:
    """
    Main synchronous logic to process literature.
    Orchestrates the entire workflow from identifier extraction to saving the result.
    """
    try:
        update_task_status("任务开始", 0, f"开始处理: {source.get('title', 'N/A')}")

        # 1. Extract authoritative identifiers
        update_task_status("正在提取标识符", 10)
        identifiers, primary_type = extract_authoritative_identifiers(source)
        logger.info(
            f"提取到标识符: {identifiers.model_dump_json(exclude_none=True)} (主要类型: {primary_type})"
        )
        if not any([identifiers.doi, identifiers.arxiv_id, identifiers.fingerprint]):
            raise ValueError("无法提取任何有效标识符，任务终止。")

            # Lazily import fetchers to avoid circular dependencies and scope them locally.
            from .content_fetcher import ContentFetcher
        from .metadata_fetcher import MetadataFetcher
        from .references_fetcher import ReferencesFetcher

        content_fetcher = ContentFetcher(settings)
        metadata_fetcher = MetadataFetcher(settings)
        references_fetcher = ReferencesFetcher(settings)

        # 2. Fetch content (PDF) - a blocking I/O operation.
        # This is a candidate for future optimization if I/O becomes a bottleneck.
        update_task_status("正在获取内容", 25)
        content, pdf_content, content_raw_data = (
            content_fetcher.fetch_content_waterfall(identifiers, source, None)
        )
        logger.info(f"内容获取完成: {content_raw_data.get('download_status', '未知')}")

        # 3. Fetch metadata - multiple blocking I/O calls.
        # This is a prime candidate for parallel execution (e.g., using a thread pool).
        update_task_status("正在获取元数据", 40, f"使用 {primary_type} 标识符")
        metadata, metadata_raw_data = metadata_fetcher.fetch_metadata_waterfall(
            identifiers, primary_type, source
        )
        if not metadata:
            raise ValueError("所有元数据源均失败，无法处理文献。")
        logger.info(f"成功获取元数据，标题: {metadata.title}")

        # 4. Fetch references - more blocking I/O.
        # Also a candidate for parallel execution.
        update_task_status("正在获取参考文献", 65)
        references, references_raw_data = references_fetcher.fetch_references_waterfall(
            identifiers, primary_type, pdf_content
        )
        logger.info(f"成功获取 {len(references)} 条参考文献")

        # 5. Consolidate and save the final result.
        update_task_status("正在整合与保存", 90)
        task_info = TaskInfoModel(
            task_id=task_id,
            status="completed",
            processing_stages=[
                "identifier_extraction",
                "content_fetch",
                "metadata_fetch",
                "reference_fetch",
                "data_integration",
            ],
        )

        final_literature = LiteratureModel(
            identifiers=identifiers,
            metadata=metadata,
            references=references,
            content=content,
            source_docs={
                "initial_source": source,
                "content_sources": content_raw_data,
                "metadata_sources": metadata_raw_data,
                "reference_sources": references_raw_data,
            },
            task_info=task_info,
        )

        literature_id = _save_literature_sync(final_literature, settings)
        update_task_status("任务完成", 100, f"文献已保存，ID: {literature_id}")

        return literature_id

    except Exception as e:
        logger.error(f"处理任务 {task_id} 时出错: {e}", exc_info=True)
        update_task_status("任务失败", details=str(e))
        raise


@celery_app.task(bind=True, name="process_literature_task")
def process_literature_task(self, source: Dict[str, Any]) -> str:
    """
    Celery task to process a single literature source. Main entry point for the worker.
    """
    task_id = self.request.id
    logger.info(f"接收到文献处理任务 {task_id}")
    logger.info(f"来源数据: {source}")

    try:
        # Direct synchronous call, resolving the original event loop conflict.
        result_id = _process_literature(task_id, source)
        return result_id
    except Exception as e:
        logger.exception(f"任务 {task_id} 执行失败: {e}", exc_info=True)
        self.update_state(
            state="FAILURE", meta={"exc_type": type(e).__name__, "exc_message": str(e)}
        )
        raise
