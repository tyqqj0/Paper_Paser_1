"""
New API endpoints for literature resolution (0.2 version).

This module implements the unified resolution endpoint as specified in the 0.2 API design.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from literature_parser_backend.models.literature import LiteratureCreateRequestDTO
from literature_parser_backend.worker.tasks import process_literature_task
from literature_parser_backend.db.alias_dao import AliasDAO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resolve", tags=["文献解析"])


@router.post(
    "",
    summary="Resolve literature aliases to LIDs",
    status_code=status.HTTP_202_ACCEPTED,
)
async def resolve_literature(
    literature_data: LiteratureCreateRequestDTO,
) -> JSONResponse:
    """
    Resolve external literature aliases (DOI, URL, etc.) to internal LIDs.
    
    This endpoint implements the "Ensure Literature Exists" operation:
    - If aliases already exist, returns 200 OK with corresponding LIDs immediately
    - If aliases need resolution, returns 202 Accepted with a Task ID for async processing
    
    Args:
        literature_data: Literature identifiers and metadata for resolution
        
    Returns:
        - 200 OK: Literature already exists, with LID and resource URL
        - 202 Accepted: Task created for async resolution, with task_id and status URL
    """
    try:
        effective_values = literature_data.get_effective_values()

        # 🔍 DEBUG: Check data transformation
        logger.info(f"📋 Original request data: {literature_data.model_dump()}")
        logger.info(f"📋 Effective values: {effective_values}")

        if not any(
            key in effective_values
            for key in ["doi", "arxiv_id", "url", "pdf_url", "title"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one identifier must be provided.",
            )

        logger.info(f"Resolve request received with data: {effective_values}")

        # Check alias system first for immediate resolution
        alias_dao = AliasDAO()
        existing_lid = await alias_dao.resolve_to_lid(effective_values)
        
        if existing_lid:
            # Literature already exists, return immediately with 200 OK
            logger.info(f"Literature resolved immediately: LID={existing_lid}")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Literature already exists in system.",
                    "lid": existing_lid,
                    "resource_url": f"/api/literatures/{existing_lid}",  # New 0.2 API path
                    "status": "resolved"
                },
            )

        # No alias match found, create asynchronous task
        logger.info("Literature not found, creating resolution task")
        task = process_literature_task.delay(effective_values)

        logger.info(f"Resolution task {task.id} created.")

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Literature resolution task created.",
                "task_id": task.id,
                "status_url": f"/api/tasks/{task.id}",  # New 0.2 API path
                "stream_url": f"/api/tasks/{task.id}/stream"  # New 0.2 SSE path
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve endpoint error: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error.",
        )
