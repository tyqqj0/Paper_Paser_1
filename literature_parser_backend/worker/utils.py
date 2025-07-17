"""
Worker utility functions.
"""

import hashlib
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from celery import current_task
from loguru import logger

from ..models.literature import (
    AuthorModel,
    IdentifiersModel,
    MetadataModel,
)


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
    """
    identifiers = IdentifiersModel(doi=None, arxiv_id=None, fingerprint=None)
    primary_type = None

    # Extract DOI
    doi_pattern = r"10\.\d{4,}/[^\s]+"
    if source.get("url") and "doi.org" in source["url"]:
        if match := re.search(doi_pattern, source["url"]):
            identifiers.doi = match.group()
            primary_type = "doi"
    if not identifiers.doi and source.get("doi"):
        identifiers.doi = source["doi"]
        primary_type = "doi"

    # Extract ArXiv ID
    if source.get("url") and "arxiv.org" in source["url"]:
        if match := re.search(r"arxiv\.org/(?:abs|pdf)/([^/?]+)", source["url"]):
            identifiers.arxiv_id = match.group(1).replace(".pdf", "")
            if not primary_type:
                primary_type = "arxiv"
    if not identifiers.arxiv_id and source.get("arxiv_id"):
        identifiers.arxiv_id = source["arxiv_id"]
        if not primary_type:
            primary_type = "arxiv"

    return identifiers, primary_type or "unknown"


def convert_grobid_to_metadata(grobid_data: Dict[str, Any]) -> MetadataModel:
    """Convert GROBID output to MetadataModel."""
    header = grobid_data.get("TEI", {}).get("teiHeader", {}).get("fileDesc", {})
    title_stmt = header.get("titleStmt", {})
    
    title = title_stmt.get("title", {}).get("#text")
    
    authors = []
    author_list = header.get("sourceDesc", {}).get("biblStruct", {}).get("analytic", {}).get("author", [])
    if isinstance(author_list, dict): # handle case where there is only one author
        author_list = [author_list]

    for author_data in author_list:
        pers_name = author_data.get("persName", {})
        forenames = [fn.get("#text") for fn in pers_name.get("forename", []) if isinstance(fn, dict)]
        surname = pers_name.get("surname", {}).get("#text")
        full_name = " ".join(forenames) + (f" {surname}" if surname else "")
        authors.append(AuthorModel(name=full_name.strip()))

    return MetadataModel(
        title=title or "Unknown Title",
        authors=authors,
        year=None,
        journal=None,
        abstract=header.get("profileDesc", {}).get("abstract", {}).get("#text"),
        source_priority=["grobid"],
    ) 