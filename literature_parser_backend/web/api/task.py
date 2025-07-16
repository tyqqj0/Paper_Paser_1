"""Task status query API endpoints."""

from datetime import datetime
from typing import Any, Dict

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from literature_parser_backend.models.task import TaskStatus, TaskStatusDTO
from literature_parser_backend.worker.celery_app import celery_app

router = APIRouter(prefix="/task", tags=["任务管理"])


@router.get("/{task_id}", summary="Query task status")
async def get_task_status(task_id: str) -> TaskStatusDTO:
    """
    Query the status and result of a Celery task.

    Args:
        task_id: The Celery task ID.

    Returns:
        The task status information.
    """
    try:
        # Get task result from Celery backend
        task_result = AsyncResult(task_id, app=celery_app)

        # 基础任务状态映射
        status_mapping = {
            "PENDING": TaskStatus.PENDING,
            "STARTED": TaskStatus.PROCESSING,
            "SUCCESS": TaskStatus.SUCCESS,
            "FAILURE": TaskStatus.FAILURE,
            "RETRY": TaskStatus.PROCESSING,
            "REVOKED": TaskStatus.FAILURE,  # 取消视为失败
        }

        task_status = status_mapping.get(task_result.status, TaskStatus.PENDING)
        current_time = datetime.now()

        # 构建响应数据
        response_data: Dict[str, Any] = {
            "task_id": task_id,
            "status": task_status,
            "literature_id": None,
            "progress_percentage": None,
            "error_info": None,
            "created_at": current_time,  # 临时使用当前时间
            "updated_at": current_time,
        }

        if task_result.status == "SUCCESS":
            # 成功状态：提取文献ID和其他信息
            result = task_result.result
            if isinstance(result, dict):
                response_data.update(
                    literature_id=result.get("literature_id"),
                    resource_url=(
                        f"/api/literature/{result['literature_id']}"
                        if result.get("literature_id")
                        else None
                    ),
                )
            response_data["progress_percentage"] = 100

        elif task_result.status == "FAILURE":
            # 失败状态：提取错误信息
            error_msg = str(task_result.info) if task_result.info else "Task failed"
            response_data["error_info"] = {
                "error_type": "TaskExecutionError",
                "error_message": error_msg,
            }

        elif task_result.status == "PENDING":
            # 等待状态
            response_data["progress_percentage"] = 0

        elif task_result.status in ["STARTED", "RETRY"]:
            # 处理中状态：尝试获取进度信息
            if hasattr(task_result, "info") and isinstance(task_result.info, dict):
                info = task_result.info
                response_data.update(
                    stage=info.get("stage", "Processing"),
                    progress_percentage=info.get("progress", 0),
                )

        elif task_result.status == "REVOKED":
            # 已取消状态
            response_data["error_info"] = {
                "error_type": "TaskCancelled",
                "error_message": "任务被管理员取消",
            }

        logger.info(f"查询任务状态: {task_id} -> {task_status}")

        # 使用Pydantic模型验证和返回
        return TaskStatusDTO(**response_data)

    except Exception as e:
        logger.error(f"Error querying task status for {task_id}: {e!s}")

        # Return 404 for invalid task IDs
        if "Invalid task ID" in str(e) or "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            ) from e

        # Return 500 for other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query task status: {e!s}",
        ) from e


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
