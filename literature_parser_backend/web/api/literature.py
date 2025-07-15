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


def _extract_convenience_fields(literature) -> dict:
    """从文献对象中提取便利字段"""
    convenience_data = {
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
        
        # 尝试不同来源的元数据
        sources = ['crossref', 'semantic_scholar', 'grobid']
        
        for source in sources:
            source_data = metadata_dict.get(source, {})
            if source_data and isinstance(source_data, dict):
                # 提取标题
                if not convenience_data["title"] and source_data.get('title'):
                    convenience_data["title"] = source_data['title']
                
                # 提取年份
                if not convenience_data["year"]:
                    year_val = source_data.get('year') or source_data.get('published-online', {}).get('date-parts', [[None]])[0][0]
                    if year_val:
                        try:
                            convenience_data["year"] = int(year_val)
                        except (ValueError, TypeError):
                            pass
                
                # 提取期刊
                if not convenience_data["journal"]:
                    convenience_data["journal"] = (
                        source_data.get('journal') or 
                        source_data.get('venue') or
                        source_data.get('container-title', [None])[0] if isinstance(source_data.get('container-title'), list) else source_data.get('container-title')
                    )
                
                # 提取作者
                if not convenience_data["authors"]:
                    authors_data = source_data.get('authors', []) or source_data.get('author', [])
                    if authors_data:
                        author_names = []
                        for author in authors_data:
                            if isinstance(author, dict):
                                # 不同格式的作者数据
                                name = (
                                    author.get('name') or
                                    author.get('full_name') or  
                                    f"{author.get('given', '')} {author.get('family', '')}".strip() or
                                    author.get('given') or
                                    author.get('family')
                                )
                                if name:
                                    author_names.append(name)
                            elif isinstance(author, str):
                                author_names.append(author)
                        
                        if author_names:
                            convenience_data["authors"] = author_names
    
    return convenience_data


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

        # 手动提取便利字段数据
        convenience_data = _extract_convenience_fields(literature)
        
        # 转换为摘要DTO
        summary = LiteratureSummaryDTO(
            id=str(literature.id),
            identifiers=literature.identifiers,
            metadata=literature.metadata,
            content=literature.content.model_dump() if literature.content else {},
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
            id=str(literature.id),
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
