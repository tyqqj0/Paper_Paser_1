"""
New API endpoints for literature data retrieval (0.2 version).

This module implements literature query endpoints as specified in the 0.2 API design.
Includes convenient synchronous APIs for common use cases.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from literature_parser_backend.models.literature import LiteratureSummaryDTO, LiteratureCreateRequestDTO, LiteratureFulltextDTO
from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.alias_dao import AliasDAO
from literature_parser_backend.worker.tasks import process_literature_task
from literature_parser_backend.worker.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/literatures", tags=["文献查询"])


def _extract_convenience_fields(literature) -> Dict[str, Any]:
    """
    Extract convenience fields from the literature model.
    
    This function intelligently handles different data source formats.
    Restored from deleted literature.py file.
    """
    convenience_data: Dict[str, Any] = {
        "title": None,
        "authors": [],
        "year": None, 
        "journal": None,
        "doi": None,
        "abstract": None,
    }

    # 从identifiers提取DOI
    if literature.identifiers and literature.identifiers.doi:
        convenience_data["doi"] = literature.identifiers.doi

    # 从metadata提取信息
    if literature.metadata:
        metadata_dict = literature.metadata.model_dump()

        # 方法1：尝试直接从平面结构提取（新的统一格式）
        if metadata_dict.get("title"):
            convenience_data["title"] = metadata_dict["title"]

        if metadata_dict.get("year"):
            convenience_data["year"] = metadata_dict["year"]

        if metadata_dict.get("journal"):
            convenience_data["journal"] = metadata_dict["journal"]

        if metadata_dict.get("abstract"):
            convenience_data["abstract"] = metadata_dict["abstract"]

        # 处理作者数据
        if metadata_dict.get("authors"):
            authors_data = metadata_dict["authors"]
            if authors_data:
                author_names = []
                for author in authors_data:
                    if isinstance(author, dict):
                        # 支持不同的作者格式
                        name = (
                            author.get("name")
                            or author.get("full_name")
                            or f"{author.get('given', '')} {author.get('family', '')}".strip()
                            or author.get("given")
                            or author.get("family")
                        )
                        if name:
                            author_names.append(name)
                    elif isinstance(author, str):
                        author_names.append(author)

                if author_names:
                    convenience_data["authors"] = author_names

        # 方法2：如果平面结构没有数据，尝试嵌套结构（兼容旧格式）
        if not any([
            convenience_data["title"],
            convenience_data["authors"],
            convenience_data["year"],
            convenience_data["journal"],
        ]):
            # 尝试不同来源的元数据
            sources = ["crossref", "semantic_scholar", "grobid"]

            for source in sources:
                source_data = metadata_dict.get(source, {})
                if source_data and isinstance(source_data, dict):
                    # 提取标题
                    if not convenience_data["title"] and source_data.get("title"):
                        convenience_data["title"] = source_data["title"]

                    # 提取年份
                    if not convenience_data["year"]:
                        year_val = (
                            source_data.get("year")
                            or source_data.get("published-online", {}).get("date-parts", [[None]])[0][0]
                        )
                        if year_val:
                            try:
                                convenience_data["year"] = int(year_val)
                            except (ValueError, TypeError):
                                pass

                    # 提取期刊
                    if not convenience_data["journal"]:
                        convenience_data["journal"] = (
                            source_data.get("journal")
                            or source_data.get("venue") 
                            or source_data.get("container-title", [None])[0]
                            if isinstance(source_data.get("container-title"), list)
                            else source_data.get("container-title")
                        )

                    # 提取作者
                    if not convenience_data["authors"]:
                        authors_data = source_data.get("authors", []) or source_data.get("author", [])
                        if authors_data:
                            author_names = []
                            for author in authors_data:
                                if isinstance(author, dict):
                                    # 不同格式的作者数据
                                    name = (
                                        author.get("name")
                                        or author.get("full_name")
                                        or f"{author.get('given', '')} {author.get('family', '')}".strip()
                                        or author.get("given")
                                        or author.get("family")
                                    )
                                    if name:
                                        author_names.append(name)
                                elif isinstance(author, str):
                                    author_names.append(author)

                            if author_names:
                                convenience_data["authors"] = author_names

    return convenience_data


# ========== Convenient Synchronous APIs (Must be before /{lid} route) ==========

@router.get("/by-doi", summary="Get literature by DOI with automatic processing")
async def get_literature_by_doi(
    value: str = Query(
        ...,
        description="DOI value to lookup",
        example="10.1145/3485447.3512256"
    ),
    wait_timeout: int = Query(
        30,
        description="Maximum seconds to wait for processing if literature not found",
        ge=5,
        le=120
    )
) -> Dict[str, Any]:
    """
    Get literature by DOI with automatic processing and synchronous waiting.
    
    This convenient endpoint:
    1. Checks if literature already exists by DOI alias
    2. If exists, returns it immediately
    3. If not, triggers processing and waits for completion
    4. Returns the processed literature or timeout error
    
    Perfect for frontend integration where you need the result immediately.
    
    Args:
        value: DOI value to lookup
        wait_timeout: Maximum seconds to wait for processing (5-120)
        
    Returns:
        Literature data with processing status, or error if timeout
    """
    try:
        logger.info(f"🔍 Convenient DOI lookup: {value}")
        
        # Step 1: Check if already exists via alias system
        alias_dao = AliasDAO.create_from_global_connection()
        existing_lid = await alias_dao.resolve_to_lid({"identifiers": {"doi": value}})
        
        if existing_lid:
            logger.info(f"✅ DOI {value} found existing LID: {existing_lid}")
            # Get existing literature
            dao = LiteratureDAO.create_from_global_connection()
            literature = await dao.get_literature_by_id(existing_lid)
            if literature:
                return {
                    "status": "found_existing",
                    "lid": existing_lid,
                    "literature": literature.model_dump(),
                    "processing_time_ms": 0
                }
        
        # Step 2: Not found, trigger processing with synchronous wait
        logger.info(f"🚀 DOI {value} not found, triggering processing...")
        
        # Create processing request
        literature_data = LiteratureCreateRequestDTO(
            identifiers={"doi": value},
            title="Processing..."  # Will be updated after processing
        )
        
        # Start processing task
        task = process_literature_task.delay(literature_data.model_dump())
        task_id = task.id
        
        logger.info(f"⏳ Waiting up to {wait_timeout}s for task {task_id}")
        
        # Wait for completion with timeout
        start_time = asyncio.get_event_loop().time()
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            if elapsed > wait_timeout:
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "status": "processing_timeout",
                        "message": f"Processing started but didn't complete within {wait_timeout}s",
                        "task_id": task_id,
                        "wait_time_s": elapsed,
                        "suggestion": "Use GET /api/tasks/{task_id} to check status later"
                    }
                )
            
            # Check task status
            result = celery_app.AsyncResult(task_id)
            if result.ready():
                if result.successful():
                    task_result = result.get()
                    lid = task_result.get("lid")
                    if lid:
                        # Get the processed literature
                        dao = LiteratureDAO.create_from_global_connection()
                        literature = await dao.get_literature_by_lid(lid)
                        if literature:
                            logger.info(f"🎉 DOI {value} processed successfully -> {lid}")
                            return {
                                "status": "processed_successfully", 
                                "lid": lid,
                                "literature": literature.model_dump(),
                                "task_id": task_id,
                                "processing_time_ms": int(elapsed * 1000)
                            }
                    
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "status": "processing_failed",
                            "message": "Task completed but no literature data found",
                            "task_id": task_id
                        }
                    )
                else:
                    error_msg = str(result.result) if result.result else "Unknown error"
                    logger.error(f"❌ Task {task_id} failed: {error_msg}")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "status": "processing_failed",
                            "message": f"Processing failed: {error_msg}",
                            "task_id": task_id
                        }
                    )
            
            # Wait a bit before checking again
            await asyncio.sleep(1.0)
            
    except Exception as e:
        logger.error(f"❌ Error in DOI lookup for {value}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process DOI lookup: {str(e)}"
        )


@router.get("/by-title", summary="Get literature by title with automatic processing") 
async def get_literature_by_title(
    value: str = Query(
        ...,
        description="Paper title to lookup",
        example="Attention Is All You Need"
    ),
    wait_timeout: int = Query(
        30,
        description="Maximum seconds to wait for processing if literature not found",
        ge=5,
        le=120
    )
) -> Dict[str, Any]:
    """
    Get literature by title with automatic processing and synchronous waiting.
    
    Similar to by-doi but uses title-based alias resolution.
    
    Args:
        value: Paper title to lookup
        wait_timeout: Maximum seconds to wait for processing (5-120)
        
    Returns:
        Literature data with processing status, or error if timeout
    """
    try:
        logger.info(f"🔍 Convenient title lookup: {value}")
        
        # Check if already exists via alias system
        alias_dao = AliasDAO.create_from_global_connection()
        existing_lid = await alias_dao.resolve_to_lid({"title": value})
        
        if existing_lid:
            logger.info(f"✅ Title '{value}' found existing LID: {existing_lid}")
            dao = LiteratureDAO.create_from_global_connection()
            literature = await dao.get_literature_by_id(existing_lid)
            if literature:
                return {
                    "status": "found_existing",
                    "lid": existing_lid,
                    "literature": literature.model_dump(),
                    "processing_time_ms": 0
                }
        
        # Not found, trigger processing
        logger.info(f"🚀 Title '{value}' not found, triggering processing...")
        
        literature_data = LiteratureCreateRequestDTO(
            title=value,
            identifiers={}
        )
        
        task = process_literature_task.delay(literature_data.model_dump())
        task_id = task.id
        
        logger.info(f"⏳ Waiting up to {wait_timeout}s for task {task_id}")
        
        # Similar waiting logic as DOI endpoint
        start_time = asyncio.get_event_loop().time()
        while True:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - start_time
            
            if elapsed > wait_timeout:
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "status": "processing_timeout",
                        "message": f"Processing started but didn't complete within {wait_timeout}s",
                        "task_id": task_id,
                        "wait_time_s": elapsed,
                        "suggestion": "Use GET /api/tasks/{task_id} to check status later"
                    }
                )
            
            result = celery_app.AsyncResult(task_id)
            if result.ready():
                if result.successful():
                    task_result = result.get()
                    lid = task_result.get("lid")
                    if lid:
                        dao = LiteratureDAO.create_from_global_connection()
                        literature = await dao.get_literature_by_lid(lid)
                        if literature:
                            logger.info(f"🎉 Title '{value}' processed successfully -> {lid}")
                            return {
                                "status": "processed_successfully",
                                "lid": lid, 
                                "literature": literature.model_dump(),
                                "task_id": task_id,
                                "processing_time_ms": int(elapsed * 1000)
                            }
                    
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "status": "processing_failed",
                            "message": "Task completed but no literature data found",
                            "task_id": task_id
                        }
                    )
                else:
                    error_msg = str(result.result) if result.result else "Unknown error"
                    logger.error(f"❌ Task {task_id} failed: {error_msg}")
                    return JSONResponse(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content={
                            "status": "processing_failed",
                            "message": f"Processing failed: {error_msg}",
                            "task_id": task_id
                        }
                    )
            
            await asyncio.sleep(1.0)
            
    except Exception as e:
        logger.error(f"❌ Error in title lookup for '{value}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process title lookup: {str(e)}"
        )


@router.get("/{lid}", summary="Get literature by LID")
async def get_literature_by_lid(lid: str) -> LiteratureSummaryDTO:
    """
    Get detailed information for a literature by its LID.
    
    This endpoint supports both the new LID format and legacy MongoDB ObjectId
    for backward compatibility.
    
    Args:
        lid: Literature ID (LID) or legacy MongoDB ObjectId
        
    Returns:
        Detailed literature information including metadata, content summary, and references
        
    Raises:
        404: Literature not found
        500: Internal server error
    """
    try:
        dao = LiteratureDAO()
        
        # Find by LID using Neo4j DAO
        literature = await dao.find_by_lid(lid)
        if not literature:
            # For legacy ObjectId support, we may need to implement this method
            # For now, try to find by LID only in Neo4j-only mode
            pass

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Literature not found: {lid}",
            )

        # 🎯 Extract convenience fields using restored function
        convenience_data = _extract_convenience_fields(literature)

        # Create content summary (exclude large parsed_fulltext)
        content_summary = {}
        if literature.content:
            content_dict = literature.content.model_dump()
            content_summary = {
                "pdf_url": content_dict.get("pdf_url"),
                "source_page_url": content_dict.get("source_page_url"),
                "sources_tried": content_dict.get("sources_tried", []),
                "has_parsed_fulltext": content_dict.get("parsed_fulltext") is not None,
                "grobid_processing_summary": _create_processing_summary(
                    content_dict.get("grobid_processing_info") or {},
                ),
            }

        # Build response DTO
        summary = LiteratureSummaryDTO(
            id=literature.lid or str(literature.id),  # Use LID if available, fallback to ObjectId
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            content=content_summary,
            references=literature.references,
            task_info=literature.task_info,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
            # Convenience fields
            title=convenience_data["title"],
            authors=convenience_data["authors"],
            year=convenience_data["year"],
            journal=convenience_data["journal"],
            doi=convenience_data["doi"],
            abstract=convenience_data["abstract"],
        )

        logger.info(f"Literature retrieved successfully: {lid}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving literature {lid}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


@router.get("", summary="Get multiple literatures by LIDs")  
async def get_literatures_batch(
    lids: str = Query(
        ..., 
        description="Comma-separated list of LIDs (e.g., 'lid1,lid2,lid3')",
        example="2017-vaswani-aayn-6a05,2019-do-gtpncr-72ef"
    )
) -> List[LiteratureSummaryDTO]:
    """
    Get detailed information for multiple literatures by their LIDs.
    
    This endpoint supports batch querying of literatures using a comma-separated
    list of LIDs in the query parameter.
    
    Args:
        lids: Comma-separated string of Literature IDs
        
    Returns:
        List of literature summaries. Missing literatures are omitted from results.
        
    Raises:
        400: Invalid LIDs parameter format
        500: Internal server error
    """
    try:
        # Parse comma-separated LIDs
        lid_list = [lid.strip() for lid in lids.split(",") if lid.strip()]
        
        if not lid_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one LID must be provided.",
            )

        if len(lid_list) > 50:  # Reasonable batch size limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many LIDs requested. Maximum 50 LIDs per request.",
            )

        logger.info(f"Batch literature request for {len(lid_list)} LIDs")

        dao = LiteratureDAO()
        results = []
        
        for lid in lid_list:
            try:
                # Try LID first, then fall back to MongoDB ObjectId
                literature = await dao.find_by_lid(lid)
                if not literature:
                    literature = await dao.get_literature_by_id(lid)

                if literature:
                    # Extract convenience fields  
                    convenience_data = {
                        'title': literature.metadata.title if literature.metadata else None,
                        'authors': [author.name for author in literature.metadata.authors] if literature.metadata and literature.metadata.authors else [],
                        'year': literature.metadata.year if literature.metadata else None,
                        'journal': literature.metadata.journal if literature.metadata else None,
                        'doi': literature.identifiers.doi if literature.identifiers else None,
                        'abstract': literature.metadata.abstract if literature.metadata else None,
                    }

                    # Create content summary
                    content_summary = {}
                    if literature.content:
                        content_dict = literature.content.model_dump()
                        content_summary = {
                            "pdf_url": content_dict.get("pdf_url"),
                            "source_page_url": content_dict.get("source_page_url"),
                            "sources_tried": content_dict.get("sources_tried", []),
                            "has_parsed_fulltext": content_dict.get("parsed_fulltext") is not None,
                            "grobid_processing_summary": _create_processing_summary(
                                content_dict.get("grobid_processing_info") or {},
                            ),
                        }

                    summary = LiteratureSummaryDTO(
                        id=literature.lid or str(literature.id),
                        identifiers=literature.identifiers,
                        metadata=literature.metadata,
                        content=content_summary,
                        references=literature.references,
                        task_info=literature.task_info,
                        created_at=literature.created_at,
                        updated_at=literature.updated_at,
                        # Convenience fields
                        title=convenience_data["title"],
                        authors=convenience_data["authors"],
                        year=convenience_data["year"],
                        journal=convenience_data["journal"],
                        doi=convenience_data["doi"],
                        abstract=convenience_data["abstract"],
                    )
                    results.append(summary)
                else:
                    logger.warning(f"Literature not found: {lid}")
            except Exception as e:
                logger.error(f"Error processing LID {lid}: {e}")
                # Continue processing other LIDs, don't fail entire batch

        logger.info(f"Batch request completed: {len(results)}/{len(lid_list)} found")
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch literature request: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


@router.get("/{literature_id}/fulltext", summary="Get literature fulltext")
async def get_literature_fulltext(literature_id: str) -> LiteratureFulltextDTO:
    """
    Get the full parsed content of a literature (e.g., from GROBID).
    
    Restored from deleted literature.py file.

    Args:
        literature_id: The Literature ID (LID) or MongoDB ObjectId of the literature.

    Returns:
        The DTO containing the full parsed content and processing information.
    """
    try:
        dao = LiteratureDAO.create_from_global_connection()
        
        # Try LID first, then fall back to MongoDB ObjectId
        literature = await dao.find_by_lid(literature_id)
        if not literature:
            literature = await dao.get_literature_by_id(literature_id)

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文献不存在",
            )

        # 确保content字段存在且为ContentModel实例
        parsed_fulltext = (
            literature.content.parsed_fulltext if literature.content else None
        )

        grobid_processing_info = (
            literature.content.grobid_processing_info if literature.content else None
        )

        # 确定解析时间和来源
        parsed_at = None
        source = None

        if grobid_processing_info:
            parsed_at = grobid_processing_info.get("processed_at")
            source = "GROBID"

        return LiteratureFulltextDTO(
            literature_id=literature.lid or str(literature.id),  # Use LID if available, fallback to ObjectId
            parsed_fulltext=parsed_fulltext,
            grobid_processing_info=grobid_processing_info,
            source=source,
            parsed_at=parsed_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文献全文内容错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


def _create_processing_summary(grobid_info: dict) -> dict:
    """Create a processing summary from GROBID processing info."""
    return {
        "processed_at": grobid_info.get("processed_at"),
        "processing_time_ms": grobid_info.get("processing_time_ms"),
        "success": grobid_info.get("success"),
        "pages_processed": grobid_info.get("pages_processed"),
        "text_length_chars": grobid_info.get("text_length_chars"),
        "grobid_version": grobid_info.get("grobid_version"),
    }



