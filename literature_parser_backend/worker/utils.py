"""
Worker utility functions.
"""

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
) -> Tuple[IdentifiersModel, str, Optional[Dict[str, Any]]]:
    """
    Extract authoritative identifiers from source data.
    Priority: DOI > ArXiv ID > Other academic IDs > Generated fingerprint

    Enhanced with URL mapping service for better URL support.

    Returns:
        Tuple of (identifiers, primary_type, url_validation_info)
    """
    identifiers = IdentifiersModel(doi=None, arxiv_id=None, fingerprint=None)
    primary_type = None
    url_validation_info = None

    # 首先尝试使用URL映射服务（新功能）
    if source.get("url"):
        try:
            # 先进行URL验证
            from ..services.url_mapping.core.service import URLMappingService
            temp_service = URLMappingService(enable_url_validation=True)

            # 直接使用URL验证功能
            if not temp_service._validate_url(source["url"]):
                # URL验证失败，记录详细信息并抛出异常
                url_validation_info = {
                    "status": "failed",
                    "error": f"URL {source['url']} 无法访问或不存在",
                    "original_url": source["url"],
                    "validation_details": {
                        "error_type": "url_not_accessible",
                        "validation_time": datetime.now().isoformat(),
                    }
                }
                logger.warning(f"URL验证失败: {source['url']}")
                raise ValueError(f"URL验证失败: {url_validation_info['error']}")

            # URL验证成功，继续使用旧版本的URL映射服务
            from ..services.url_mapper import get_url_mapping_service as get_old_service
            old_url_service = get_old_service()
            mapping_result = old_url_service.map_url_sync(source["url"])

            # 记录URL验证成功信息
            url_validation_info = {
                "status": "success",
                "original_url": source["url"],
                "validation_details": {
                    "validation_time": datetime.now().isoformat(),
                }
            }

            # URL验证已经在上面完成，这里直接处理映射结果

            if mapping_result.doi:
                identifiers.doi = mapping_result.doi
                primary_type = "doi"
            elif mapping_result.arxiv_id:
                identifiers.arxiv_id = mapping_result.arxiv_id
                if not primary_type:
                    primary_type = "arxiv"

            # 如果URL映射服务找到了标识符，直接返回
            if identifiers.doi or identifiers.arxiv_id:
                return identifiers, primary_type or "unknown", url_validation_info

        except Exception as e:
            # 如果是URL验证失败，直接抛出
            if "URL验证失败" in str(e):
                raise e

            # 其他异常，回退到传统方法
            logger.warning(f"URL映射服务失败，回退到传统方法: {e}")
            # 记录URL映射服务失败信息
            if source.get("url"):
                url_validation_info = {
                    "status": "skipped",
                    "error": f"URL映射服务异常: {str(e)}",
                    "original_url": source["url"],
                    "validation_details": {
                        "error_type": "service_error",
                        "validation_time": datetime.now().isoformat(),
                    }
                }

    # 传统方法作为备用（保持向后兼容）
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

    return identifiers, primary_type or "unknown", url_validation_info


def convert_grobid_to_metadata(grobid_data: Dict[str, Any]) -> MetadataModel:
    """Convert GROBID output to MetadataModel."""
    header = grobid_data.get("TEI", {}).get("teiHeader", {}).get("fileDesc", {})
    title_stmt = header.get("titleStmt", {})

    title = title_stmt.get("title", {}).get("#text")

    authors = []
    author_list = (
        header.get("sourceDesc", {})
        .get("biblStruct", {})
        .get("analytic", {})
        .get("author", [])
    )
    if isinstance(author_list, dict):  # handle case where there is only one author
        author_list = [author_list]

    for author_data in author_list:
        pers_name = author_data.get("persName", {})
        forenames = [
            fn.get("#text")
            for fn in pers_name.get("forename", [])
            if isinstance(fn, dict)
        ]
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
