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
from ..services import CrossRefClient, GrobidClient, SemanticScholarClient
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
    # Use the full db_url from settings, which should include authSource
    mongo_url = settings.db_url
    client = pymongo.MongoClient(str(mongo_url))
    db = client[settings.db_base]
    collection = db.literatures

    try:
        doc_data = literature.model_dump(by_alias=True)

        # Ensure _id is not set to None, so MongoDB generates it.
        if "_id" in doc_data and doc_data["_id"] is None:
            del doc_data["_id"]

        # Ensure created_at and updated_at are set
        now = datetime.now()
        if "created_at" not in doc_data or doc_data["created_at"] is None:
            doc_data["created_at"] = now
        doc_data["updated_at"] = now

        result = collection.insert_one(doc_data)
        inserted_id = str(result.inserted_id)
        logger.info(f"Literature saved to MongoDB with ID: {inserted_id}")
        return inserted_id
    finally:
        client.close()


# Load settings and initialize clients
settings = Settings()
grobid_client = GrobidClient(settings)
crossref_client = CrossRefClient(settings)
semantic_scholar_client = SemanticScholarClient(settings)


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

    :param source: Source data dictionary
    :return: Tuple of (IdentifiersModel, primary_identifier_type)
    """
    identifiers = IdentifiersModel()
    primary_type = None

    # Extract DOI with highest priority
    doi_pattern = r"10\.\d{4,}/[^\s]+"

    # Check URL for DOI
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
                identifiers.arxiv_id = arxiv_match.group(1).replace(".pdf", "")
                if not primary_type:
                    primary_type = "arxiv"

    # Check direct DOI field
    if source.get("doi") and not identifiers.doi:
        identifiers.doi = source["doi"]
        primary_type = "doi"

    # Check direct ArXiv ID
    if source.get("arxiv_id") and not identifiers.arxiv_id:
        identifiers.arxiv_id = source["arxiv_id"]
        if not primary_type:
            primary_type = "arxiv"

    # Generate fingerprint if no other identifiers found
    if not identifiers.doi and not identifiers.arxiv_id:
        title = source.get("title", "")
        # Assuming authors is a list of dicts with 'name'
        authors_list = source.get("authors", [])
        authors_str = ", ".join(
            [author.get("name", "") for author in authors_list if author],
        )
        year = source.get("year", "")

        content = f"{title}|{authors_str}|{year}".lower().strip()
        if content and content != "||":
            identifiers.fingerprint = hashlib.md5(content.encode()).hexdigest()[:16]
            primary_type = "fingerprint"

    return identifiers, primary_type or "fingerprint"


def fetch_metadata_waterfall(
    identifiers: IdentifiersModel,
    pdf_content: Optional[bytes] = None,
) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
    """
    Fetch metadata using waterfall approach: CrossRef/Semantic Scholar -> GROBID fallback.

    :param identifiers: Authoritative identifiers
    :param pdf_content: Optional PDF content for GROBID fallback
    :return: Tuple of (MetadataModel, raw_data_dict)
    """
    metadata = None
    raw_data = {}

    update_task_status("正在获取元数据", 20, "尝试从外部API获取")

    # Try CrossRef first for DOI
    if identifiers.doi:
        try:
            logger.info(f"Fetching metadata from CrossRef for DOI: {identifiers.doi}")
            crossref_data = crossref_client.get_metadata_by_doi(identifiers.doi)
            if crossref_data:
                raw_data["crossref"] = crossref_data
                metadata = convert_crossref_to_metadata(crossref_data)
                logger.info("Successfully got metadata from CrossRef")

        except Exception as e:
            logger.warning(f"CrossRef API failed: {e}")

    # Try Semantic Scholar if CrossRef failed or for ArXiv
    if not metadata and (identifiers.doi or identifiers.arxiv_id):
        try:
            identifier = identifiers.doi or identifiers.arxiv_id
            logger.info(f"Fetching metadata from Semantic Scholar for: {identifier}")
            s2_data = semantic_scholar_client.get_metadata(identifier)
            if s2_data:
                raw_data["semantic_scholar"] = s2_data
                if not metadata:  # Only use if CrossRef didn't provide data
                    metadata = convert_semantic_scholar_to_metadata(s2_data)
                logger.info("Successfully got metadata from Semantic Scholar")

        except Exception as e:
            logger.warning(f"Semantic Scholar API failed: {e}")

    # Fallback to GROBID if APIs failed and we have PDF
    if not metadata and pdf_content:
        try:
            update_task_status("正在解析PDF元数据", 40, "使用GROBID解析PDF标题信息")
            logger.info("Falling back to GROBID for metadata extraction")
            grobid_data = grobid_client.process_header_only(pdf_content)
            if grobid_data:
                raw_data["grobid_header"] = grobid_data
                metadata = convert_grobid_to_metadata(grobid_data)
                logger.info("Successfully extracted metadata from GROBID")

        except Exception as e:
            logger.error(f"GROBID fallback failed: {e}")

    return metadata, raw_data


def fetch_references_waterfall(
    identifiers: IdentifiersModel,
    pdf_content: Optional[bytes] = None,
) -> Tuple[List[ReferenceModel], Dict[str, Any]]:
    """
    Fetch references using waterfall approach: Semantic Scholar -> GROBID fallback.

    :param identifiers: Authoritative identifiers
    :param pdf_content: Optional PDF content for GROBID fallback
    :return: Tuple of (List[ReferenceModel], raw_data_dict)
    """
    references = []
    raw_data = {}

    update_task_status("正在获取参考文献", 60, "尝试从Semantic Scholar获取")

    # Try Semantic Scholar first
    if identifiers.doi or identifiers.arxiv_id:
        try:
            identifier = identifiers.doi or identifiers.arxiv_id
            logger.info(f"Fetching references from Semantic Scholar for: {identifier}")
            s2_refs = semantic_scholar_client.get_references(identifier)
            if s2_refs:
                raw_data["semantic_scholar_refs"] = s2_refs
                references = convert_semantic_scholar_references(s2_refs)
                logger.info(
                    f"Successfully got {len(references)} references from Semantic Scholar",
                )

        except Exception as e:
            logger.warning(
                f"Semantic Scholar API for references failed: {e}. Will try GROBID fallback.",
            )

    # Fallback to GROBID if Semantic Scholar fails and we have PDF
    if not references and pdf_content:
        try:
            update_task_status("正在解析PDF参考文献", 70, "使用GROBID解析PDF参考文献")
            logger.info("Falling back to GROBID for reference extraction")
            # Corrected to use process_pdf which is the actual method in GrobidClient
            grobid_data = grobid_client.process_pdf(
                pdf_content, include_raw_citations=True,
            )
            if grobid_data and grobid_data.get("references"):
                raw_data["grobid_refs"] = grobid_data["references"]
                references = convert_grobid_references(grobid_data["references"])
                logger.info(
                    f"Successfully extracted {len(references)} references from GROBID",
                )
        except Exception as e:
            logger.error(f"GROBID fallback for references failed: {e}")

    return references, raw_data


def convert_crossref_to_metadata(crossref_data: Dict[str, Any]) -> MetadataModel:
    """Converts CrossRef API response to a standardized MetadataModel."""
    message = crossref_data.get("message", {})
    authors = []
    if "author" in crossref_data:
        for author in crossref_data["author"]:
            author_name = f"{author.get('given', '')} {author.get('family', '')}".strip()
            if author_name:
                authors.append(AuthorModel(name=author_name))
    return MetadataModel(
        title=crossref_data.get("title", [""])[0],
        authors=authors,
        year=message.get("published-print") or message.get("published-online"),
        journal=message.get("container-title", [None])[0],
        abstract=message.get("abstract"),
        source_of_data=["crossref"],
    )


def convert_semantic_scholar_to_metadata(s2_data: Dict[str, Any]) -> MetadataModel:
    """Converts Semantic Scholar API response to a standardized MetadataModel."""
    authors = []
    if "authors" in s2_data:
        for author in s2_data["authors"]:
            if author and author.get("name"):
                authors.append(
                    AuthorModel(name=author["name"], s2_id=author.get("authorId")),
                )
    return MetadataModel(
        title=s2_data.get("title"),
        authors=authors,
        year=s2_data.get("year"),
        journal=s2_data.get("venue"),
        abstract=s2_data.get("abstract"),
        source_of_data=["semantic_scholar"],
    )


def convert_grobid_to_metadata(grobid_data: Dict[str, Any]) -> MetadataModel:
    """Converts GROBID header response to a standardized MetadataModel."""
    # Assuming TEI XML format is parsed into a dict-like structure
    tei_header = grobid_data.get("TEI", {}).get("teiHeader", {})
    file_desc = tei_header.get("fileDesc", {})
    title_stmt = file_desc.get("titleStmt", {})
    title = title_stmt.get("title", {}).get("#text")

    authors = []
    if "authors" in grobid_data:
        for author in grobid_data["authors"]:
            full_name = author.get("name")
            if full_name:
                authors.append(AuthorModel(name=full_name))

    publication_stmt = file_desc.get("publicationStmt", {})
    date_info = publication_stmt.get("date", {})
    year = date_info.get("@when")

    abstract = (
        file_desc.get("profileDesc", {}).get("abstract", {}).get("p", {}).get("#text")
    )

    return MetadataModel(
        title=title,
        authors=authors,
        year=year,
        journal=source_desc.get("monogr", {}).get("title", {}).get("#text"),
        abstract=abstract,
        source_of_data=["grobid"],
    )


def convert_semantic_scholar_references(
    s2_refs: List[Dict[str, Any]],
) -> List[ReferenceModel]:
    """Converts Semantic Scholar references to a list of ReferenceModels."""
    references = []
    for ref in s2_refs:
        # s2_refs from get_references is a list of dicts, where each dict
        # has 'citedPaper' which contains the actual paper details.
        paper_details = ref.get("citedPaper", {})
        if not paper_details:
            continue

        authors = [
            AuthorModel(name=author["name"])
            for author in paper_details.get("authors", [])
            if author and author.get("name")
        ]
        parsed_data = {
            "title": paper_details.get("title"),
            "authors": authors,
            "year": paper_details.get("year"),
            "journal": paper_details.get("venue"),
            "identifiers": IdentifiersModel(
                doi=paper_details.get("doi"),
                arxiv_id=paper_details.get("arxivId"),
                semantic_scholar_id=paper_details.get("paperId"),
            ),
            "source_of_data": ["semantic_scholar"],
        }
        references.append(ReferenceModel(**parsed_data))
    return references


def convert_grobid_references(
    grobid_refs: List[Dict[str, Any]],
) -> List[ReferenceModel]:
    """Converts GROBID parsed references to a list of ReferenceModels."""
    # This is a placeholder. GROBID's reference output is complex (TEI XML).
    # A full implementation requires a dedicated TEI XML parser.
    logger.warning(
        "GROBID reference parsing is a placeholder and not fully implemented.",
    )
    return []


def _process_literature_sync(task_id: str, source: Dict[str, Any]) -> str:
    """
    Synchronous core logic for processing literature.
    This is the main pipeline executed by the Celery task.
    """
    logger.info(f"Starting literature processing for task_id: {task_id}")
    update_task_status("任务开始", 0, f"正在处理来源: {source.get('url') or source}")

    try:
        # Step 1: Extract identifiers
        update_task_status("提取标识符", 5, "从来源URL或数据中提取DOI/ArXiv ID")
        identifiers, primary_id_type = extract_authoritative_identifiers(source)
        logger.info(f"Extracted identifiers: {identifiers}, Primary: {primary_id_type}")
        if not any(identifiers.model_dump().values()):
            raise ValueError("无法提取任何有效的文献标识符。")

        # Step 2: Fetch PDF content if applicable
        pdf_content = None
        if primary_id_type == "arxiv":
            update_task_status("下载PDF", 10, f"从ArXiv下载PDF: {identifiers.arxiv_id}")
            try:
                # Assuming ContentFetcher is adapted to be sync
                from .content_fetcher import ContentFetcher

                content_fetcher = ContentFetcher(settings)
                # This needs to be a synchronous method call
                pdf_content = content_fetcher.fetch_pdf_from_arxiv_id(
                    identifiers.arxiv_id,
                )
                logger.info(
                    f"Successfully downloaded PDF from ArXiv. Size: {len(pdf_content)} bytes",
                )
            except Exception as e:
                logger.error(f"Failed to download PDF: {e}")
                update_task_status("PDF下载失败", 15, f"错误: {e}")

        content = ContentModel(
            pdf_content_available=bool(pdf_content),
            # pdf_content is not stored in DB model
            xml_content_available=False,  # GROBID XML can be stored if needed
            source_of_data=["arxiv_pdf_downloader" if pdf_content else "none"],
        )

        # Step 3: Fetch metadata
        update_task_status("获取元数据", 20)
        metadata, metadata_raw_data = fetch_metadata_waterfall(identifiers, pdf_content)
        if not metadata:
            logger.warning("Metadata could not be fetched. Creating fallback metadata.")
            title = source.get("title", "Unknown Title")
            if not title:
                title = "Unknown Title"
            metadata = MetadataModel(
                title=title,
                authors=[],
                year=None,
                journal=None,
                abstract=None,
                source_of_data=["fallback"],
            )

        # logger.info(f"Successfully fetched metadata with title: {metadata.title}")

        # Step 4: Fetch references
        update_task_status("获取参考文献", 65)
        references, references_raw_data = fetch_references_waterfall(
            identifiers, pdf_content,
        )
        logger.info(f"Fetched {len(references)} references.")

        # Step 5: Data integration
        update_task_status("整合数据", 80)

        # Step 6: Create task info
        task_info = TaskInfoModel(
            task_id=task_id,
            created_at=datetime.now(),
            # Simplified stages
            processing_stages=[
                "identifier_extraction",
                "metadata_fetch",
                "reference_fetch",
                "data_integration",
            ],
            total_processing_time=0,  # Placeholder
            success=True,
        )

        # Step 7: Create final literature model
        literature = LiteratureModel(
            identifiers=identifiers,
            metadata=metadata,
            content=content,
            references=references,
            task_info=task_info,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            # Raw data for debugging
            raw_data={
                "metadata": metadata_raw_data,
                "references": references_raw_data,
            },
        )

        # Step 8: Save to MongoDB
        update_task_status("保存到数据库", 90)
        try:
            literature_id = _save_literature_sync(literature, settings)
            logger.info(f"Successfully saved literature with ID: {literature_id}")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to save to database: {e}", exc_info=True)
            # Create a placeholder ID for return if save fails
            literature_id = f"failed_to_save_{task_id[:8]}"
            logger.warning(f"Returning placeholder literature ID: {literature_id}")

        update_task_status("完成", 100, f"文献ID: {literature_id}")

        return {
            "literature_id": str(literature_id),  # Ensure it's a string
            "status": "success",
            "message": f"Successfully processed and saved literature {literature_id}",
        }

    except Exception as e:
        logger.error(
            f"Unhandled error in literature processing pipeline for task {task_id}: {e}",
            exc_info=True,
        )
        update_task_status("失败", 100, f"错误: {e!s}")
        # Re-raise the exception to mark the Celery task as FAILED
        raise


@celery_app.task(bind=True, name="process_literature_task")
def process_literature_task(self, source: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task entry point for literature processing.

    This function is a lightweight wrapper that calls the main synchronous
    processing logic, handling task state and exceptions.

    :param source: Dictionary with 'url', 'doi', 'arxiv_id', etc.
    :return: Dictionary with processing result, including the literature_id.
    """
    try:
        return _process_literature_sync(self.request.id, source)
    except Exception:
        # The exception is already logged in the sync function
        # Celery will automatically mark the task as failed
        raise  # Re-raising is important for Celery to see the failure
