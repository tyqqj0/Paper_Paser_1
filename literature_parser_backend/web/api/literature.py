"""Literature processing API endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.models.literature import (
    LiteratureCreateRequestDTO,
    LiteratureFulltextDTO,
    LiteratureModel,
    LiteratureSummaryDTO,
)
from literature_parser_backend.worker.tasks import process_literature_task

router = APIRouter(prefix="/literature", tags=["文献处理"])


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

        logger.info(f"Received submission, creating task with data: {effective_values}")

        # Directly create a task without any synchronous checks.
        task = process_literature_task.delay(effective_values)

        logger.info(f"Task {task.id} created for processing.")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Literature processing task created.",
                "task_id": task.id,
                "status_url": f"/api/task/status/{task.id}",
            },
        )

    except Exception as e:
        logger.error(f"Error submitting literature: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error.",
        )


@router.get("/{literature_id}", summary="Get literature summary")
async def get_literature_summary(literature_id: str) -> LiteratureSummaryDTO:
    """
    Get summary information for a literature.

    Args:
        literature_id: The MongoDB ObjectId of the literature.

    Returns:
        The literature summary information.
    """
    try:
        dao = LiteratureDAO()
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
            id=str(literature.id),
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
        literature_id: The MongoDB ObjectId of the literature.

    Returns:
        The DTO containing the full parsed content and processing information.
    """
    try:
        dao = LiteratureDAO()
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
            literature_id=str(literature.id),
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
