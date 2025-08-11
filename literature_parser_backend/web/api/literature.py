"""Literature processing API endpoints with SSE support."""

import asyncio
import json
from typing import Any, Dict, Union

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.db.alias_dao import AliasDAO
from literature_parser_backend.models.literature import (
    LiteratureCreateRequestDTO,
    LiteratureFulltextDTO,
    LiteratureModel,
    LiteratureSummaryDTO,
)
from literature_parser_backend.worker.tasks import process_literature_task
from literature_parser_backend.web.api.task import UnifiedStatusManager

router = APIRouter(prefix="/literature", tags=["文献处理"])


async def task_status_stream(task_id: str):
    """
    任务状态SSE事件流生成器

    持续监控任务状态变化，只在状态改变时推送事件。
    任务完成时推送literature_id并结束流。
    """
    manager = UnifiedStatusManager()
    last_status_hash = None

    logger.info(f"Starting SSE stream for task: {task_id}")

    try:
        while True:
            # 获取当前任务状态
            current_status = await manager.get_unified_status(task_id)

            # 计算状态哈希，只在变化时推送
            status_dict = current_status.model_dump()
            current_hash = hash(str(status_dict))

            if current_hash != last_status_hash:
                # 推送状态更新事件
                logger.debug(f"Task {task_id} status changed, pushing update")
                yield f"event: status\n"
                yield f"data: {current_status.model_dump_json()}\n\n"
                last_status_hash = current_hash

            # 检查URL验证错误
            if current_status.url_validation_status == "failed":
                url_error_data = {
                    "event": "url_validation_failed",
                    "error_type": "URLValidationError",
                    "error": current_status.url_validation_error,
                    "original_url": current_status.original_url,
                    "task_id": task_id
                }
                logger.warning(f"Task {task_id} URL validation failed: {current_status.url_validation_error}")
                yield f"event: error\n"
                yield f"data: {json.dumps(url_error_data)}\n\n"

            # 检查组件级错误
            if current_status.literature_status:
                component_status = current_status.literature_status.component_status
                for comp_name in ['metadata', 'content', 'references']:
                    comp_detail = getattr(component_status, comp_name, None)
                    if comp_detail and comp_detail.status.value == "failed" and comp_detail.error_info:
                        comp_error_data = {
                            "event": "component_failed",
                            "component": comp_name,
                            "error_type": comp_detail.error_info.get("error_type", "UnknownError"),
                            "error": comp_detail.error_info.get("error_message", "组件处理失败"),
                            "error_details": comp_detail.error_info,
                            "task_id": task_id
                        }
                        logger.warning(f"Task {task_id} component {comp_name} failed: {comp_detail.error_info}")
                        yield f"event: error\n"
                        yield f"data: {json.dumps(comp_error_data)}\n\n"

            # 检查任务是否完成
            if current_status.execution_status.value in ["completed", "failed"]:
                if current_status.execution_status.value == "completed":
                    # 推送完成事件，包含literature_id
                    completion_data = {
                        "event": "completed",
                        "literature_id": current_status.literature_id,
                        "resource_url": f"/api/literature/{current_status.literature_id}"
                    }
                    logger.info(f"Task {task_id} completed, literature_id: {current_status.literature_id}")
                    yield f"event: completed\n"
                    yield f"data: {json.dumps(completion_data)}\n\n"
                else:
                    # 推送失败事件，包含详细错误信息
                    error_data = {
                        "event": "failed",
                        "error": "任务处理失败",
                        "task_id": task_id
                    }

                    # 如果有URL验证错误，添加到失败事件中
                    if current_status.url_validation_error:
                        error_data["error_type"] = "URLValidationError"
                        error_data["error"] = current_status.url_validation_error
                        error_data["original_url"] = current_status.original_url

                    logger.warning(f"Task {task_id} failed: {error_data}")
                    yield f"event: failed\n"
                    yield f"data: {json.dumps(error_data)}\n\n"

                # 任务结束，关闭流
                logger.info(f"Ending SSE stream for task: {task_id}")
                break

            # 等待1秒后再次检查状态
            await asyncio.sleep(1)

    except Exception as e:
        # 推送错误事件
        error_data = {
            "event": "error",
            "error": str(e),
            "task_id": task_id
        }
        logger.error(f"SSE stream error for task {task_id}: {e}")
        yield f"event: error\n"
        yield f"data: {json.dumps(error_data)}\n\n"


def _extract_convenience_fields(literature: LiteratureModel) -> Dict[str, Any]:
    """
    Extract convenience fields from the literature model.

    This function intelligently handles different data source formats.
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
        if not any(
            [
                convenience_data["title"],
                convenience_data["authors"],
                convenience_data["year"],
                convenience_data["journal"],
            ],
        ):
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
                            or source_data.get("published-online", {}).get(
                                "date-parts",
                                [[None]],
                            )[0][0]
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
                        authors_data = source_data.get(
                            "authors",
                            [],
                        ) or source_data.get(
                            "author",
                            [],
                        )
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


@router.post(
    "",
    summary="Submit literature for processing",
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_literature(
    literature_data: LiteratureCreateRequestDTO,
) -> JSONResponse:
    """
    Submit a literature for asynchronous processing.
    This endpoint ONLY creates a task and returns immediately.
    All deduplication logic is handled by the asynchronous worker.
    """
    try:
        effective_values = literature_data.get_effective_values()

        if not any(
            key in effective_values
            for key in ["doi", "arxiv_id", "url", "pdf_url", "title"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one identifier must be provided.",
            )

        logger.info(f"Received submission, checking aliases first with data: {effective_values}")

        # NEW: Check alias system first for immediate resolution
        alias_dao = AliasDAO.create_from_global_connection()
        existing_lid = await alias_dao.resolve_to_lid(effective_values)
        
        if existing_lid:
            # Literature already exists, return immediately with 200 OK
            logger.info(f"Literature found via alias resolution: LID={existing_lid}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Literature already exists in system.",
                    "lid": existing_lid,
                    "resource_url": f"/api/literature/{existing_lid}",
                    "status": "exists"
                },
            )

        # No alias match found, create asynchronous task as before
        logger.info("No existing literature found, creating processing task")
        task = process_literature_task.delay(effective_values)

        logger.info(f"Task {task.id} created for processing.")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Literature processing task created.",
                "task_id": task.id,
                "status_url": f"/api/task/{task.id}",
            },
        )

    except Exception as e:
        logger.error(f"Error submitting literature: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error.",
        )


@router.post("/stream", summary="Submit literature with SSE")
async def create_literature_stream(
    literature_data: LiteratureCreateRequestDTO,
) -> StreamingResponse:
    """
    提交文献处理并返回SSE连接

    这个端点会立即返回一个SSE连接，通过该连接实时推送任务状态更新。
    当任务完成时，会推送包含literature_id的完成事件。

    Args:
        literature_data: 文献创建请求数据

    Returns:
        SSE流响应，包含任务状态更新和完成事件
    """
    try:
        effective_values = literature_data.get_effective_values()

        if not any(
            key in effective_values
            for key in ["doi", "arxiv_id", "url", "pdf_url", "title"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one identifier must be provided.",
            )

        logger.info(f"Received SSE submission, checking aliases first with data: {effective_values}")

        # NEW: Check alias system first for immediate resolution
        alias_dao = AliasDAO.create_from_global_connection()
        existing_lid = await alias_dao.resolve_to_lid(effective_values)
        
        if existing_lid:
            # Literature already exists, return immediate completion event
            logger.info(f"Literature found via alias resolution for SSE: LID={existing_lid}")
            
            async def immediate_completion():
                completion_data = {
                    "event": "completed",
                    "literature_id": existing_lid,
                    "resource_url": f"/api/literature/{existing_lid}",
                    "message": "Literature already exists in system"
                }
                yield f"event: completed\n"
                yield f"data: {json.dumps(completion_data)}\n\n"
            
            return StreamingResponse(
                immediate_completion(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Cache-Control",
                }
            )

        # No alias match found, create asynchronous task as before
        logger.info("No existing literature found, creating SSE processing task")
        task = process_literature_task.delay(effective_values)
        logger.info(f"Task {task.id} created for SSE processing.")

        # 返回SSE流
        return StreamingResponse(
            task_status_stream(task.id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Nginx优化
                "Access-Control-Allow-Origin": "*",  # CORS支持
                "Access-Control-Allow-Headers": "Cache-Control",
            }
        )

    except Exception as e:
        logger.error(f"Error creating SSE literature stream: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error.",
        )


@router.get("/{literature_id}", summary="Get literature summary")
async def get_literature_summary(literature_id: str) -> LiteratureSummaryDTO:
    """
    Get summary information for a literature.

    Args:
        literature_id: The Literature ID (LID) or MongoDB ObjectId of the literature.

    Returns:
        The literature summary information.
    """
    try:
        dao = LiteratureDAO()
        
        # Try LID first, then fall back to MongoDB ObjectId
        literature = await dao.find_by_lid(literature_id)
        if not literature:
            literature = await dao.get_literature_by_id(literature_id)

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文献不存在",
            )

        # 手动提取便利字段数据
        convenience_data = _extract_convenience_fields(literature)

        # 创建不包含大型parsed_fulltext的content字段
        content_summary = {}
        if literature.content:
            content_dict = literature.content.model_dump()
            # 排除大型字段，只保留基本信息
            content_summary = {
                "pdf_url": content_dict.get("pdf_url"),
                "source_page_url": content_dict.get("source_page_url"),
                "sources_tried": content_dict.get("sources_tried", []),
                # 只包含处理信息的摘要，不包含实际的parsed_fulltext
                "has_parsed_fulltext": content_dict.get("parsed_fulltext") is not None,
                "grobid_processing_summary": _create_processing_summary(
                    content_dict.get("grobid_processing_info") or {},
                ),
            }

        # 转换为摘要DTO
        summary = LiteratureSummaryDTO(
            id=literature.lid or str(literature.id),  # Use LID if available, fallback to ObjectId
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            content=content_summary,
            references=literature.references,
            task_info=literature.task_info,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
            # 明确传递便利字段
            title=convenience_data["title"],
            authors=convenience_data["authors"],
            year=convenience_data["year"],
            journal=convenience_data["journal"],
            doi=convenience_data["doi"],
            abstract=convenience_data["abstract"],
        )

        logger.info(f"获取文献摘要成功: {literature_id}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文献摘要错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e


def _create_processing_summary(grobid_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a summary of GROBID processing information without large content.

    Args:
        grobid_info: Full GROBID processing information

    Returns:
        Summarized processing information
    """
    if not grobid_info:
        return {}

    return {
        "status": grobid_info.get("status"),
        "processed_at": grobid_info.get("processed_at"),
        "processing_time_ms": grobid_info.get("processing_time_ms"),
        "text_length_chars": grobid_info.get("text_length_chars"),
        "grobid_version": grobid_info.get("grobid_version"),
    }


@router.get("/{literature_id}/fulltext", summary="Get literature fulltext")
async def get_literature_fulltext(literature_id: str) -> LiteratureFulltextDTO:
    """
    Get the full parsed content of a literature (e.g., from GROBID).

    Args:
        literature_id: The Literature ID (LID) or MongoDB ObjectId of the literature.

    Returns:
        The DTO containing the full parsed content and processing information.
    """
    try:
        dao = LiteratureDAO()
        
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

    except Exception as e:
        logger.error(f"获取文献全文内容错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}",
        ) from e
