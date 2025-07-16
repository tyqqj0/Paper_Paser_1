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
import requests
from celery import Task, current_task, states
from pymongo.mongo_client import MongoClient

from ..models.literature import (
    AuthorModel,
    IdentifiersModel,
    LiteratureCreateRequestDTO,
    LiteratureModel,
    MetadataModel,
    ReferenceModel,
    TaskInfoModel,
)
from ..services import GrobidClient, SemanticScholarClient
from ..services.crossref import CrossRefClient
from ..settings import Settings
from .celery_app import celery_app
from .content_fetcher import ContentFetcher

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
    client: MongoClient[Dict[str, Any]] = pymongo.MongoClient(str(mongo_url))
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


def update_task_status(
    stage: str,
    progress: Optional[int] = None,
    details: Optional[str] = None,
) -> None:
    """Update the current task's status with stage information."""
    if current_task:
        meta: Dict[str, Any] = {
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
        }
        if progress is not None:
            meta["progress"] = progress
        if details:
            meta["details"] = details

        current_task.update_state(
            state="PROGRESS",
            meta={"stage": stage, "progress": progress, "details": details},
        )
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
    identifiers = IdentifiersModel(doi=None, arxiv_id=None, fingerprint=None)
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
            identifiers.fingerprint = hashlib.sha256(content.encode()).hexdigest()[:16]
            primary_type = "fingerprint"

    return identifiers, primary_type or "fingerprint"


def _fetch_from_crossref(
    doi: str,
) -> Tuple[Optional[MetadataModel], Optional[Dict[str, Any]]]:
    """Fetch metadata from CrossRef."""
    try:
        crossref_client = CrossRefClient()
        crossref_data = crossref_client.get_metadata_by_doi(doi)
        if crossref_data and crossref_data.get("title"):
            metadata = convert_crossref_to_metadata(crossref_data)
            logger.info(f"Successfully got metadata from CrossRef for DOI: {doi}")
            return metadata, crossref_data
    except Exception as e:
        logger.warning(f"CrossRef API for DOI {doi} failed: {e}")
    return None, None


def _fetch_from_semantic_scholar(
    identifier: str,
    id_type: str,
) -> Tuple[Optional[MetadataModel], Optional[Dict[str, Any]]]:
    """Fetch metadata from Semantic Scholar."""
    try:
        s2_client = SemanticScholarClient()
        s2_data = s2_client.get_metadata(identifier, id_type)
        if s2_data and s2_data.get("title"):
            metadata = convert_semantic_scholar_to_metadata(s2_data)
            logger.info(
                f"Successfully got metadata from S2 for {id_type}: {identifier}",
            )
            return metadata, s2_data
    except Exception as e:
        logger.warning(f"S2 API for {id_type} {identifier} failed: {e}")
    return None, None


def _fetch_from_grobid(
    pdf_content: bytes,
) -> Tuple[Optional[MetadataModel], Optional[Dict[str, Any]]]:
    """Fetch metadata from GROBID."""
    if not pdf_content:
        return None, None
    try:
        grobid_client = GrobidClient()
        header_content = grobid_client.process_header_only(pdf_content)
        if header_content and header_content.get("TEI"):
            metadata = convert_grobid_to_metadata(header_content)
            logger.info("Successfully got metadata from GROBID")
            return metadata, header_content
    except Exception as e:
        logger.warning(f"GROBID processing failed: {e}")
    return None, None


def fetch_metadata_waterfall(
    identifiers: IdentifiersModel,
    pdf_content: Optional[bytes] = None,
) -> Tuple[Optional[MetadataModel], Dict[str, Any]]:
    """
    Fetch metadata using a waterfall approach: CrossRef -> Semantic Scholar -> GROBID.

    :param identifiers: Authoritative identifiers
    :param pdf_content: PDF content for GROBID fallback
    :return: A tuple of MetadataModel and a dictionary with raw data from sources.
    """
    metadata: Optional[MetadataModel] = None
    raw_data: Dict[str, Any] = {}

    # 1. Try CrossRef if DOI is available
    if identifiers.doi:
        metadata, raw_data["crossref"] = _fetch_from_crossref(identifiers.doi)

    # 2. Try Semantic Scholar if CrossRef fails or wasn't tried
    if not metadata and (identifiers.arxiv_id or identifiers.doi):
        try:
            identifier_to_use = identifiers.arxiv_id or identifiers.doi
            if identifier_to_use:
                logger.info(
                    "Fetching metadata from Semantic Scholar for: "
                    f"{identifier_to_use}",
                )
                s2_data = semantic_scholar_client.get_metadata(identifier_to_use)
                if s2_data:
                    raw_data["semantic_scholar"] = s2_data
                    metadata = convert_semantic_scholar_to_metadata(s2_data)
                    logger.info(
                        f"Successfully got metadata from S2 for {identifier_to_use}",
                    )

        except Exception as e:
            logger.warning(
                "Semantic Scholar API for references failed: %s. "
                "Will try GROBID fallback.",
                e,
            )

    # 3. Fallback to GROBID if we have PDF content
    if not metadata and pdf_content:
        metadata, raw_data["grobid"] = _fetch_from_grobid(pdf_content)

    return metadata, raw_data


def fetch_references_waterfall(
    identifiers: IdentifiersModel,
    pdf_content: Optional[bytes],
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
            if identifier:
                logger.info(
                    f"Fetching references from Semantic Scholar for: {identifier}",
                )
                s2_refs = semantic_scholar_client.get_references(identifier)
                if s2_refs:
                    raw_data["semantic_scholar_refs"] = s2_refs
                    references = convert_semantic_scholar_references(s2_refs)
                    logger.info(
                        f"Successfully got {len(references)} references from Semantic Scholar",
                    )

        except Exception as e:
            logger.warning(
                "Semantic Scholar API for references failed: %s. "
                "Will try GROBID fallback.",
                e,
            )

    # Fallback to GROBID if Semantic Scholar fails and we have PDF
    if not references and pdf_content:
        try:
            update_task_status("正在解析PDF参考文献", 70, "使用GROBID解析PDF参考文献")
            logger.info("Falling back to GROBID for reference extraction")
            # Corrected to use process_pdf which is the actual method in GrobidClient
            grobid_data = grobid_client.process_pdf(
                pdf_content,
                include_raw_citations=True,
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
    """Convert CrossRef API response to MetadataModel."""
    title = crossref_data.get("title", [None])[0]
    authors_data = crossref_data.get("author", [])
    authors = []
    for author in authors_data:
        name = f"{author.get('given', '')} {author.get('family', '')}".strip()
        if name:
            authors.append(AuthorModel(name=name))

    year = None
    published = crossref_data.get("published-online", {}) or crossref_data.get(
        "published-print",
        {},
    )
    if "date-parts" in published and published["date-parts"][0][0]:
        year = int(published["date-parts"][0][0])

    journal = (
        crossref_data.get("container-title", [None])[0]
        if crossref_data.get("container-title")
        else None
    )
    abstract = crossref_data.get("abstract")
    if abstract:
        # Clean up abstract XML tags
        abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", "").strip()

    return MetadataModel(
        title=title or "Unknown Title",
        authors=authors,
        year=year,
        journal=journal,
        abstract=abstract,
        source_priority=["crossref"],
    )


def convert_semantic_scholar_to_metadata(
    s2_data: Dict[str, Any],
) -> MetadataModel:
    """Convert Semantic Scholar API response to MetadataModel."""
    authors = []
    if s2_data.get("authors"):
        for author in s2_data["authors"]:
            authors.append(
                AuthorModel(name=author["name"], s2_id=author.get("authorId")),
            )

    return MetadataModel(
        title=s2_data.get("title") or "Unknown Title",
        authors=authors,
        year=s2_data.get("year"),
        journal=(
            s2_data.get("journal", {}).get("name")
            if s2_data.get("journal")
            else s2_data.get("publicationVenue", {}).get("name")
        ),
        abstract=s2_data.get("abstract"),
        source_priority=["semantic_scholar"],
    )


def convert_grobid_to_metadata(grobid_data: Dict[str, Any]) -> MetadataModel:
    """Convert GROBID output to MetadataModel."""
    header = grobid_data.get("header", {})
    authors = []
    for author in header.get("authors", []):
        authors.append(AuthorModel(name=author["full_name"]))

    return MetadataModel(
        title=header.get("title") or "Unknown Title",
        authors=authors,
        year=int(header["year"]) if header.get("year") else None,
        journal=header.get("journal"),
        abstract=header.get("abstract"),
        source_priority=["grobid"],
    )


def _create_fallback_metadata(source_data: Dict[str, Any]) -> MetadataModel:
    """Create a fallback MetadataModel from the initial user-provided source data."""
    authors = []
    if source_data.get("authors"):
        for author_name in source_data["authors"]:
            if isinstance(author_name, str):
                authors.append(AuthorModel(name=author_name))
    return MetadataModel(
        title=source_data.get("title") or "Unknown Title",
        authors=authors,
        year=None,
        journal=None,
        abstract=None,
        source_priority=["fallback"],
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
            AuthorModel(name=author["name"], s2_id=author.get("authorId"))
            for author in paper_details.get("authors", [])
            if author and author.get("name")
        ]
        parsed_data = {
            "raw_text": paper_details.get("title", ""),  # Placeholder for raw text
            "parsed": {
                "title": paper_details.get("title"),
                "authors": [author.model_dump() for author in authors],
                "year": paper_details.get("year"),
                "journal": paper_details.get("venue"),
                "identifiers": IdentifiersModel(
                    doi=paper_details.get("externalIds", {}).get("DOI"),
                    arxiv_id=paper_details.get("externalIds", {}).get("ArXiv"),
                    fingerprint=None,
                ).model_dump(),
            },
            "source": "semantic_scholar",
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
    update_task_status(
        task_id,
        "任务开始",
        0,
        f"正在处理来源: {source.get('url') or source}",
    )

    try:
        # Step 1: Identifier Extraction
        update_task_status(
            task_id,
            "提取标识符",
            5,
            "从来源URL或数据中提取DOI/ArXiv ID",
        )
        effective_source = LiteratureCreateRequestDTO(**source).get_effective_values()
        identifiers, primary_type = extract_authoritative_identifiers(effective_source)

        logger.info(
            f"Extracted identifiers: doi={identifiers.doi} "
            f"arxiv_id={identifiers.arxiv_id} "
            f"fingerprint={identifiers.fingerprint}, "
            f"Primary: {primary_type}",
        )

        # Step 2: Content Fetching (download PDF)
        update_task_status(task_id, "下载PDF", 10)
        pdf_content: Optional[bytes] = None
        content_fetcher = ContentFetcher()
        content_model, content_raw_data = content_fetcher.fetch_content_waterfall(
            doi=identifiers.doi,
            arxiv_id=identifiers.arxiv_id,
            user_pdf_url=effective_source.get("pdf_url"),
        )
        if content_model.pdf_url:
            try:
                # This is a simplification; in a real scenario, you'd stream
                # the content from the URL to avoid loading large files into memory.
                response = requests.get(content_model.pdf_url, timeout=120)
                response.raise_for_status()
                pdf_content = response.content
                logger.info(
                    "Successfully downloaded PDF from "
                    f"{content_model.pdf_url}. Size: {len(pdf_content)} bytes",
                )
            except Exception as e:
                logger.error(
                    f"Failed to download PDF from {content_model.pdf_url}: {e}",
                )

        # Step 3: Fetch metadata
        update_task_status(task_id, "获取元数据", 20)
        metadata, metadata_raw_data = fetch_metadata_waterfall(
            identifiers,
            pdf_content,
        )
        if not metadata:
            logger.warning("Metadata could not be fetched. Creating fallback metadata.")
            metadata = _create_fallback_metadata(effective_source)

        logger.info(f"Successfully fetched metadata with title: {metadata.title}")

        # Step 4: Fetch references
        update_task_status(task_id, "获取参考文献", 65)
        references, references_raw_data = fetch_references_waterfall(
            identifiers,
            pdf_content,
        )
        logger.info(f"Fetched {len(references)} references.")

        # Step 5: Data integration
        update_task_status(task_id, "整合数据", 80)

        # Step 6: Create task info
        task_info = TaskInfoModel(
            task_id=task_id,
            created_at=datetime.now(),
        )

        # Step 7: Assemble the final literature model
        literature = LiteratureModel(
            task_info=task_info,
            identifiers=identifiers,
            metadata=metadata,
            content=content_model,
            references=references,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Step 8: Save to database
        update_task_status(task_id, "保存到数据库", 90)
        literature_id = _save_literature_sync(literature, settings)
        logger.info(f"Literature saved to MongoDB with ID: {literature_id}")

        return str(literature_id)

    except Exception as e:
        logger.error(
            f"Unhandled error in literature processing task {task_id}: {e}",
            exc_info=True,
        )
        # Ensure the task is marked as failed on unhandled exceptions
        current_task = process_literature_task.AsyncResult(task_id)
        current_task.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e),
                "details": "An unexpected error occurred during processing.",
            },
        )
        raise  # Re-raise the exception to be handled by Celery


@celery_app.task(bind=True, name="process_literature_task")
def process_literature_task(self: Task, source: Dict[str, Any]) -> Dict[str, Any]:
    """Celery task entry point for literature processing."""
    try:
        literature_id = _process_literature_sync(self.request.id, source)
        return {
            "status": "success",
            "message": f"Successfully processed and saved literature {literature_id}",
            "literature_id": literature_id,
        }
    except Exception as e:
        logger.error(
            f"Task {self.request.id} failed: {e}",
            exc_info=True,
        )
        # This return structure will be stored in the result backend on failure
        return {
            "status": "failure",
            "error": type(e).__name__,
            "message": str(e),
        }
