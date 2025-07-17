"""Task status query API endpoints."""

from datetime import datetime
from typing import Any, Dict

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ...db.dao import LiteratureDAO
from ...models.task import TaskStatus, TaskStatusDTO
from ...worker.celery_app import celery_app

router = APIRouter(prefix="/task", tags=["任务管理"])


@router.get("/{task_id}", response_model=TaskStatusDTO, summary="Query task status")
async def get_task_status(task_id: str) -> TaskStatusDTO:
    """Query the status and result of a Celery task with granular details."""
    task_result = AsyncResult(task_id, app=celery_app)
    dao = LiteratureDAO()
    
    response_data = {"task_id": task_id, "status": task_result.status.lower()}

    if task_result.info and isinstance(task_result.info, dict):
        response_data["details"] = task_result.info
        
        # If literature_id is available, fetch granular status from DB
        literature_id = task_result.info.get("literature_id")
        if literature_id:
            literature = await dao.get_literature_by_id(literature_id)
            if literature and literature.task_info:
                response_data["component_status"] = literature.task_info.component_status
                response_data["literature_id"] = literature_id

    # Handle final states
    if task_result.ready():
        if task_result.successful():
            result = task_result.result
            response_data["status"] = result.get("status", "success").lower()
            response_data["literature_id"] = result.get("literature_id")
        else:
            response_data["status"] = "failure"
            response_data["details"] = {"error": str(task_result.info)}

    return TaskStatusDTO(**response_data)


@router.delete("/{task_id}", summary="Cancel a task")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """
    Cancel a running task.

    Args:
        task_id: The Celery task ID.

    Returns:
        The result of the cancellation operation.
    """
    try:
        # Revoke the task
        celery_app.control.revoke(task_id, terminate=True)
        logger.info(f"Cancellation request sent for task: {task_id}")
        return {"message": "Task cancellation request sent"}

    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {e!s}",
        ) from e
