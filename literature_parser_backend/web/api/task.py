"""Task status query API endpoints."""

from typing import Dict

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ...db.dao import LiteratureDAO
from ...models.task import (
    TaskStatusDTO,
    TaskExecutionStatus,
    TaskResultType,
    LiteratureProcessingStatus,
)
from ...worker.celery_app import celery_app

router = APIRouter(prefix="/task", tags=["任务管理"])


class UnifiedStatusManager:
    """统一状态管理器 - 聚合任务和文献状态"""

    def __init__(self):
        self.dao = LiteratureDAO()

    def _map_celery_status(self, celery_status: str, task_info: dict = None) -> TaskExecutionStatus:
        """映射Celery状态到标准任务执行状态"""
        celery_status = celery_status.upper()

        # 检查任务结果中的业务状态
        if (task_info and
            isinstance(task_info, dict) and
            task_info.get("status") == "failed"):
            return TaskExecutionStatus.FAILED

        # 检查是否是URL验证失败的特殊情况（PROGRESS状态）
        if (celery_status == "PROGRESS" and
            task_info and
            isinstance(task_info, dict) and
            task_info.get("task_failed")):
            return TaskExecutionStatus.FAILED

        if celery_status == "PENDING":
            return TaskExecutionStatus.PENDING
        elif celery_status == "PROGRESS":
            return TaskExecutionStatus.PROCESSING
        elif celery_status == "SUCCESS":
            return TaskExecutionStatus.COMPLETED
        elif celery_status == "FAILURE":
            return TaskExecutionStatus.FAILED
        else:
            return TaskExecutionStatus.PROCESSING  # 默认为处理中

    async def get_unified_status(self, task_id: str) -> TaskStatusDTO:
        """获取统一的任务状态"""
        # 1. 获取Celery任务状态
        task_result = AsyncResult(task_id, app=celery_app)
        execution_status = self._map_celery_status(task_result.status, task_result.info)

        # 2. 获取文献详细状态
        literature_status = None
        literature_id = None
        result_type = None
        current_stage = None
        overall_progress = 0

        # 3. 获取URL验证相关信息
        url_validation_status = None
        url_validation_error = None
        original_url = None

        # 从Celery meta信息获取各种状态信息
        if task_result.info and isinstance(task_result.info, dict):
            literature_id = task_result.info.get("literature_id")
            current_stage = task_result.info.get("current_stage")
            overall_progress = task_result.info.get("progress", 0)

            # 提取URL验证信息
            url_validation_status = task_result.info.get("url_validation_status")
            url_validation_error = task_result.info.get("url_validation_error")
            original_url = task_result.info.get("original_url")

        # 如果任务完成，从结果中获取信息
        if task_result.ready() and task_result.successful():
            result = task_result.result
            if isinstance(result, dict):
                result_type = result.get("result_type")
                literature_id = result.get("literature_id")
                if result.get("status") == TaskExecutionStatus.COMPLETED:
                    execution_status = TaskExecutionStatus.COMPLETED

        # 如果任务失败
        if task_result.ready() and not task_result.successful():
            execution_status = TaskExecutionStatus.FAILED

        # 3. 获取文献的详细处理状态
        if literature_id:
            try:
                literature_status = await self.dao.get_literature_processing_status(literature_id)
                if literature_status:
                    # 如果有文献状态，使用文献的进度信息
                    overall_progress = literature_status.overall_progress
                    # 获取当前活跃的阶段
                    active_stages = []
                    if literature_status.component_status.metadata.status == "processing":
                        active_stages.append(literature_status.component_status.metadata.stage)
                    if literature_status.component_status.content.status == "processing":
                        active_stages.append(literature_status.component_status.content.stage)
                    if literature_status.component_status.references.status == "processing":
                        active_stages.append(literature_status.component_status.references.stage)

                    if active_stages:
                        current_stage = "; ".join(active_stages)
                    elif literature_status.overall_status == "completed":
                        # 区分新处理完成和重复文献
                        if result_type == "duplicate":
                            current_stage = "处理完成"
                        else:
                            current_stage = "处理完成"
                    elif literature_status.overall_status == "failed":
                        # 区分新处理失败和重复文献的历史失败状态
                        if result_type == "duplicate":
                            current_stage = "文献已存在（历史处理失败）"
                        else:
                            current_stage = "处理失败"
            except Exception as e:
                logger.warning(f"Failed to get literature status for {literature_id}: {e}")

        # 4. 构建统一响应
        return TaskStatusDTO(
            task_id=task_id,
            execution_status=execution_status,
            result_type=TaskResultType(result_type) if result_type else None,
            literature_id=literature_id,
            literature_status=literature_status,
            status=execution_status.value,  # 向后兼容
            overall_progress=overall_progress,
            current_stage=current_stage,
            # URL验证相关字段（新增）
            url_validation_status=url_validation_status,
            url_validation_error=url_validation_error,
            original_url=original_url,
            resource_url=f"/api/literatures/{literature_id}" if literature_id and execution_status == TaskExecutionStatus.COMPLETED else None
        )


@router.get(
    "/{task_id}", response_model=TaskStatusDTO, summary="查询统一任务状态",
)
async def get_task_status(task_id: str) -> TaskStatusDTO:
    """查询任务状态 - 返回统一的任务执行状态和文献处理状态"""
    try:
        manager = UnifiedStatusManager()
        return await manager.get_unified_status(task_id)
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务状态失败: {str(e)}"
        )




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
