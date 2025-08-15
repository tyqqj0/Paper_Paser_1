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
    Priority: DOI > ArXiv ID > URL mapping > Generated fingerprint

    优化策略：
    1. 优先使用直接提供的DOI/ArXiv ID（最可靠）
    2. 如果没有直接标识符，再尝试URL映射
    3. 对于已知问题域名（如Semantic Scholar），跳过URL验证

    Returns:
        Tuple of (identifiers, primary_type, url_validation_info)
    """
    identifiers = IdentifiersModel(doi=None, arxiv_id=None, fingerprint=None)
    primary_type = None
    url_validation_info = None

    # 🔍 DEBUG: Log input data structure for troubleshooting
    logger.info(f"🔍 [extract_authoritative_identifiers] Input source keys: {list(source.keys())}")
    logger.info(f"🔍 [extract_authoritative_identifiers] Input source structure: {source}")
    
    # Check for nested identifiers structure (common issue after get_effective_values)
    if "identifiers" in source:
        logger.info(f"🔍 [extract_authoritative_identifiers] Found nested identifiers: {source['identifiers']}")
        if isinstance(source["identifiers"], dict):
            nested_doi = source["identifiers"].get("doi")
            nested_arxiv = source["identifiers"].get("arxiv_id") 
            if nested_doi or nested_arxiv:
                logger.warning(f"⚠️ [extract_authoritative_identifiers] DETECTED NESTED IDENTIFIERS! This suggests get_effective_values() didn't flatten properly. DOI: {nested_doi}, ArXiv: {nested_arxiv}")

    # 🎯 优先级1：直接提供的DOI（最可靠）
    if source.get("doi"):
        identifiers.doi = source["doi"]
        primary_type = "doi"
        logger.info(f"✅ 使用直接提供的DOI: {identifiers.doi}")
        return identifiers, primary_type, url_validation_info

    # 🎯 优先级2：直接提供的ArXiv ID
    if source.get("arxiv_id"):
        identifiers.arxiv_id = source["arxiv_id"]
        primary_type = "arxiv"
        logger.info(f"✅ 使用直接提供的ArXiv ID: {identifiers.arxiv_id}")
        return identifiers, primary_type, url_validation_info

    # 🎯 优先级3：URL映射服务（如果没有直接标识符）
    if source.get("url"):
        try:
            # 检查是否为已知问题域名，跳过URL验证
            problematic_domains = [
                'semanticscholar.org',
                'scholar.google.com',
                'researchgate.net',
                # 可以根据需要添加更多域名
            ]

            skip_validation = any(domain in source["url"].lower() for domain in problematic_domains)

            if skip_validation:
                logger.info(f"🔄 跳过URL验证（已知问题域名）: {source['url']}")
                url_validation_info = {
                    "status": "skipped",
                    "reason": "known_problematic_domain",
                    "original_url": source["url"],
                    "validation_details": {
                        "skip_reason": "domain_has_anti_bot_protection",
                        "validation_time": datetime.now().isoformat(),
                    }
                }
            else:
                # 对其他域名进行URL验证
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
                    # raise ValueError(f"URL验证失败: {url_validation_info['error']}")
                    return identifiers, "unknown", url_validation_info
                else:
                    url_validation_info = {
                        "status": "success",
                        "original_url": source["url"],
                        "validation_details": {
                            "validation_time": datetime.now().isoformat(),
                        }
                    }

            # 使用新版本的URL映射服务（支持PDF重定向）
            from ..services.url_mapping import get_url_mapping_service
            url_service = get_url_mapping_service(enable_url_validation=False)  # 验证已处理或跳过
            mapping_result = url_service.map_url_sync(source["url"])

            # 处理映射结果
            if mapping_result.doi:
                identifiers.doi = mapping_result.doi
                primary_type = "doi"
                logger.info(f"✅ URL映射提取到DOI: {identifiers.doi}")
            elif mapping_result.arxiv_id:
                identifiers.arxiv_id = mapping_result.arxiv_id
                primary_type = "arxiv"
                logger.info(f"✅ URL映射提取到ArXiv ID: {identifiers.arxiv_id}")

            # 🆕 保存URL映射结果供元数据获取器使用（包括标题等信息）
            if mapping_result.is_successful():
                # 将URL映射结果添加到url_validation_info中，供后续使用
                if not url_validation_info:
                    url_validation_info = {}
                
                url_validation_info["url_mapping_result"] = {
                    "title": mapping_result.title,
                    "year": mapping_result.year,
                    "venue": mapping_result.venue,
                    "authors": mapping_result.authors,  # 🆕 添加遗漏的作者字段！
                    "source_page_url": mapping_result.source_page_url,
                    "pdf_url": mapping_result.pdf_url,
                    "source_adapter": mapping_result.source_adapter,
                    "strategy_used": mapping_result.strategy_used,
                    "confidence": mapping_result.confidence
                }
                logger.info(f"✅ URL映射提取到有用信息: title={bool(mapping_result.title)}, venue={mapping_result.venue}, authors={len(mapping_result.authors) if mapping_result.authors else 0}")

            # 如果URL映射服务找到了标识符，直接返回
            if identifiers.doi or identifiers.arxiv_id:
                return identifiers, primary_type or "unknown", url_validation_info

        except Exception as e:
            # 如果是URL验证失败，直接抛出
            if "URL验证失败" in str(e):
                # This error is now handled by returning the validation info dict
                pass

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

    # 🎯 优先级4：传统方法作为备用（保持向后兼容）
    logger.info("🔄 使用传统方法提取标识符")

    # 从URL中提取DOI
    doi_pattern = r"10\.\d{4,}/[^\s]+"
    if source.get("url") and "doi.org" in source["url"]:
        if match := re.search(doi_pattern, source["url"]):
            identifiers.doi = match.group()
            primary_type = "doi"
            logger.info(f"✅ 传统方法从URL提取到DOI: {identifiers.doi}")

    # 从URL中提取ArXiv ID
    if not identifiers.doi and source.get("url") and "arxiv.org" in source["url"]:
        if match := re.search(r"arxiv\.org/(?:abs|pdf)/([^/?]+)", source["url"]):
            identifiers.arxiv_id = match.group(1).replace(".pdf", "")
            primary_type = "arxiv"
            logger.info(f"✅ 传统方法从URL提取到ArXiv ID: {identifiers.arxiv_id}")

    # 🔍 DEBUG: Log final extraction results
    final_doi = identifiers.doi
    final_arxiv = identifiers.arxiv_id
    final_fingerprint = identifiers.fingerprint
    
    logger.info(f"🔍 [extract_authoritative_identifiers] FINAL RESULTS:")
    logger.info(f"  DOI: {final_doi}")
    logger.info(f"  ArXiv ID: {final_arxiv}")
    logger.info(f"  Fingerprint: {final_fingerprint}")
    logger.info(f"  Primary type: {primary_type or 'unknown'}")
    logger.info(f"  URL validation: {url_validation_info.get('status') if url_validation_info else 'not_performed'}")
    
    if not final_doi and not final_arxiv and not final_fingerprint:
        logger.error(f"❌ [extract_authoritative_identifiers] NO IDENTIFIERS EXTRACTED! This will cause downstream issues.")
        logger.error(f"   Source had keys: {list(source.keys())}")
        logger.error(f"   Source: {source}")

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
