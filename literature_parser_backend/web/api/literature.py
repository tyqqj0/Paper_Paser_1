"""文献处理 API 端点"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger

from literature_parser_backend.db.dao import LiteratureDAO
from literature_parser_backend.models.literature import (
    LiteratureCreateDTO,
    LiteratureFulltextDTO,
    LiteratureSummaryDTO,
)
from literature_parser_backend.worker.tasks import process_literature_task

router = APIRouter(prefix="/literature", tags=["文献处理"])


@router.post("", summary="提交文献处理请求")
async def create_literature(literature_data: LiteratureCreateDTO):
    """
    提交文献处理请求

    逻辑流程：
    1. 根据DOI或其他唯一标识符查重
    2. 如果找到现有文献，返回200和literatureId
    3. 如果未找到，启动后台任务，返回202和taskId
    """
    try:
        dao = LiteratureDAO()

        # 智能查重逻辑：DOI > ArXiv ID > 标题匹配
        existing_literature = None
        effective_values = literature_data.get_effective_values()

        # 1. 优先使用DOI查重（最可靠）
        if effective_values.get("doi"):
            logger.info(f"正在通过DOI查重: {effective_values['doi']}")
            existing_literature = await dao.find_by_doi(effective_values["doi"])

        # 2. 其次使用ArXiv ID查重
        if not existing_literature and effective_values.get("arxiv_id"):
            logger.info(f"正在通过ArXiv ID查重: {effective_values['arxiv_id']}")
            existing_literature = await dao.find_by_arxiv_id(
                effective_values["arxiv_id"],
            )

        # 3. 最后使用标题查重（最实用）
        if not existing_literature and effective_values.get("title"):
            logger.info(f"正在通过标题查重: {effective_values['title']}")
            existing_literature = await dao.find_by_title(effective_values["title"])

            # 如果精确匹配失败，尝试模糊匹配
            if not existing_literature:
                logger.info("尝试标题模糊匹配...")
                existing_literature = await dao.find_by_title_fuzzy(
                    effective_values["title"],
                    0.85,
                )

        if existing_literature:
            logger.info(f"找到现有文献: {existing_literature.id}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "文献已存在",
                    "literatureId": str(existing_literature.id),
                    "status": "exists",
                },
            )

        # 未找到现有文献，启动后台任务
        logger.info("未找到现有文献，启动后台处理任务")
        task = process_literature_task.delay(effective_values)

        logger.info(f"任务已启动，任务ID: {task.id}")
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "文献处理任务已启动",
                "taskId": task.id,
                "status": "processing",
            },
        )

    except Exception as e:
        logger.error(f"文献提交处理错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务错误: {e!s}",
        )


@router.get("/{literature_id}", summary="获取文献摘要信息")
async def get_literature_summary(literature_id: str) -> LiteratureSummaryDTO:
    """
    获取文献的摘要信息

    Args:
        literature_id: 文献的MongoDB ObjectId

    Returns:
        LiteratureSummaryDTO: 文献摘要信息
    """
    try:
        dao = LiteratureDAO()
        literature = await dao.get_literature_by_id(literature_id)

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文献不存在",
            )

        # 转换为摘要DTO
        summary = LiteratureSummaryDTO(
            id=literature.id,
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            task_info=literature.task_info,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
        )

        logger.info(f"获取文献摘要成功: {literature_id}")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文献摘要错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务错误: {e!s}",
        )


@router.get("/{literature_id}/fulltext", summary="获取文献完整内容")
async def get_literature_fulltext(literature_id: str) -> LiteratureFulltextDTO:
    """
    获取文献的完整解析内容

    Args:
        literature_id: 文献的MongoDB ObjectId

    Returns:
        LiteratureFulltextDTO: 文献完整内容
    """
    try:
        dao = LiteratureDAO()
        literature = await dao.get_literature_by_id(literature_id)

        if not literature:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文献不存在",
            )

        # 转换为完整内容DTO
        fulltext = LiteratureFulltextDTO(
            id=literature.id,
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            content=literature.content,
            references=literature.references,
            task_info=literature.task_info,
            created_at=literature.created_at,
            updated_at=literature.updated_at,
        )

        logger.info(f"获取文献完整内容成功: {literature_id}")
        return fulltext

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文献完整内容错误: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内部服务错误: {e!s}",
        )
