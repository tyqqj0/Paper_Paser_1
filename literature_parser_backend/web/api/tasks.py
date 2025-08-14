"""
New API endpoints for task management (0.2 version).

This module implements task tracking endpoints as specified in the 0.2 API design.
Uses plural form '/tasks' instead of singular '/task' for REST compliance.
"""

import json
import logging
from typing import Dict, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from literature_parser_backend.models.task import TaskStatusDTO, TaskExecutionStatus, TaskResultType, LiteratureProcessingStatus, TaskErrorInfo
from literature_parser_backend.worker.celery_app import celery_app
from literature_parser_backend.db.dao import LiteratureDAO

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["任务跟踪"])


class SimpleStatusManager:
    """简化的状态管理器 - 替代已删除的UnifiedStatusManager"""

    def __init__(self):
        self.dao = LiteratureDAO.create_from_global_connection()

    def _map_celery_status(self, celery_status: str, task_info: dict = None) -> TaskExecutionStatus:
        """映射Celery状态到标准任务执行状态"""
        celery_status = celery_status.upper()
        
        status_mapping = {
            "PENDING": TaskExecutionStatus.PENDING,
            "STARTED": TaskExecutionStatus.PROCESSING,
            "SUCCESS": TaskExecutionStatus.COMPLETED,
            "FAILURE": TaskExecutionStatus.FAILED,
            "RETRY": TaskExecutionStatus.PROCESSING,
            "REVOKED": TaskExecutionStatus.FAILED,
        }
        
        return status_mapping.get(celery_status, TaskExecutionStatus.PENDING)

    async def get_unified_status(self, task_id: str) -> TaskStatusDTO:
        """获取统一的任务状态 - 修复版，总是返回TaskStatusDTO"""
        try:
            # 从Celery获取任务状态
            result = celery_app.AsyncResult(task_id)
            
            execution_status = TaskExecutionStatus.PENDING
            literature_status_obj: Optional[LiteratureProcessingStatus] = None
            literature_id: Optional[str] = None
            error_message: Optional[str] = None
            result_type: Optional[TaskResultType] = None
            task_result: Optional[dict] = None
            overall_progress = 0
            current_stage = "任务正在等待"

            if result:
                execution_status = self._map_celery_status(result.status)
                if result.ready():
                    if result.successful():
                        task_result = result.get()
                        if isinstance(task_result, dict):
                            literature_id = task_result.get("literature_id")  # 统一使用 "literature_id"
                            if not literature_id:
                                literature_id = task_result.get("lid") # 兼容旧版

                            result_type_str = task_result.get("result_type")
                            # 确保 result_type_str 是字符串类型
                            if isinstance(result_type_str, TaskResultType):
                                result_type = result_type_str
                            elif isinstance(result_type_str, str):
                                result_type = TaskResultType(result_type_str)
                            else:
                                result_type = None
                                
                            execution_status = TaskExecutionStatus.COMPLETED
                            overall_progress = 100
                            current_stage = "处理完成"
                            
                            # 当任务为DUPLICATE时，阶段显示更具体信息
                            if result_type == TaskResultType.DUPLICATE:
                                current_stage = "文献已存在（重复）"
                            
                        else:
                            # 正常情况下，Celery成功时，结果应该是dict
                            # 如果不是，则标记为失败，并记录错误信息
                            execution_status = TaskExecutionStatus.FAILED
                            error_message = f"任务成功，但返回了意外的结果类型: {type(task_result).__name__}"
                            
                    else:  # result.failed()
                        execution_status = TaskExecutionStatus.FAILED
                        # 尝试从result.result中提取更详细的错误信息
                        error_info_dict = result.result if isinstance(result.result, dict) else {}
                        error_message = error_info_dict.get('error', str(result.result) or "未知错误")
                
                else:  # 任务未就绪
                    execution_status = TaskExecutionStatus.PROCESSING
                    # 尝试从meta中获取更详细的进度信息
                    task_meta = result.info if isinstance(result.info, dict) else {}
                    current_stage = task_meta.get("current_stage", "任务正在处理中")
                    overall_progress = task_meta.get("progress", 50) # 默认处理中为50%

            # 如果有文献ID，从数据库获取详细状态
            # 只有在任务完成，或者处理过程中获得了literature_id时才执行
            current_lit_id_for_db = literature_id
            if not current_lit_id_for_db and isinstance(result.info, dict):
                current_lit_id_for_db = result.info.get("literature_id")

            if current_lit_id_for_db:
                literature = await self.dao.find_by_lid(current_lit_id_for_db)
                if literature and literature.task_info:
                    task_info = literature.task_info
                    # 使用TaskInfoModel创建LiteratureProcessingStatus
                    literature_status_obj = LiteratureProcessingStatus(
                        literature_id=literature.lid,
                        overall_status=task_info.status,
                        overall_progress=task_info.component_status.get_overall_progress(),
                        component_status=task_info.component_status,
                        created_at=literature.created_at,
                        updated_at=literature.updated_at
                    )
                    
                    # 仅当任务未完成时，才用数据库的进度覆盖
                    if not result.ready():
                        overall_progress = literature_status_obj.overall_progress
                    
                    # --- Start of inlined get_current_stage_display logic ---
                    # 仅当任务未完成时，才用数据库的阶段信息覆盖
                    if not result.ready():
                        if task_info.status == "completed":
                            current_stage = "处理完成"
                        elif task_info.status == "failed":
                            current_stage = f"处理失败: {task_info.error_message or '未知错误'}"
                        elif task_info.component_status.references.status.value == "processing":
                            current_stage = task_info.component_status.references.stage
                        elif task_info.component_status.content.status.value == "processing":
                            current_stage = task_info.component_status.content.stage
                        elif task_info.component_status.metadata.status.value == "processing":
                            current_stage = task_info.component_status.metadata.stage
                        else:
                            current_stage = "任务正在队列中等待"
                    # --- End of inlined get_current_stage_display logic ---
            
            # 仅在任务未就绪时，从Celery meta获取更详细的URL验证状态
            if not result.ready() and isinstance(result.info, dict):
                url_validation_status = result.info.get("url_validation_status")
                if url_validation_status == "failed":
                    execution_status = TaskExecutionStatus.FAILED
                    error_message = result.info.get("url_validation_error", "URL验证失败")
                    current_stage = f"验证失败: {error_message}"
            
            error_info = None
            if error_message:
                error_info = TaskErrorInfo(
                    error_type="CeleryTaskError",
                    error_message=error_message
                )
            
            return TaskStatusDTO(
                task_id=task_id,
                execution_status=execution_status,
                literature_status=literature_status_obj,
                literature_id=literature_id,
                result_type=result_type,
                status=execution_status.value,
                overall_progress=overall_progress,
                current_stage=current_stage,
                error_info=error_info
            )

        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}", exc_info=True)
            error_info = TaskErrorInfo(
                error_type="TaskStatusQueryError",
                error_message=f"Failed to get task status: {str(e)}"
            )
            
            return TaskStatusDTO(
                task_id=task_id,
                execution_status=TaskExecutionStatus.FAILED,
                literature_status=None,
                literature_id=None,
                result_type=None,
                status=TaskExecutionStatus.FAILED.value,
                overall_progress=0,
                error_info=error_info,
                current_stage="查询任务状态时出错"
            )


@router.get(
    "/{task_id}", 
    response_model=TaskStatusDTO, 
    summary="Get task status"
)
async def get_task_status(task_id: str) -> TaskStatusDTO:
    """
    Get the current status and progress of a task.
    
    This endpoint provides unified task status information including:
    - Execution status (pending, processing, completed, failed)
    - Overall progress percentage
    - Current processing stage
    - Literature information (if completed)
    - Error details (if failed)
    
    Args:
        task_id: Unique identifier of the task to query
        
    Returns:
        Comprehensive task status information
        
    Raises:
        404: Task not found
        500: Internal server error
    """
    try:
        # Use the simplified status manager
        status_manager = SimpleStatusManager()
        task_status = await status_manager.get_unified_status(task_id)
        
        # 不再需要检查None，因为get_unified_status总是返回TaskStatusDTO
        
        logger.info(f"Task status retrieved: {task_id}")
        return task_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task status for {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}"
        ) from e


@router.get("/{task_id}/stream", summary="Stream task status updates")
async def stream_task_status(task_id: str) -> StreamingResponse:
    """
    Establish a Server-Sent Events (SSE) connection for real-time task status updates.
    
    This endpoint provides real-time progress updates for long-running literature
    processing tasks. The connection remains open until the task completes or fails.
    
    Events sent:
    - 'progress': Task progress updates with current stage and percentage
    - 'completed': Task completion with final results
    - 'failed': Task failure with error information
    
    Args:
        task_id: Unique identifier of the task to stream
        
    Returns:
        SSE streaming response with real-time task updates
        
    Raises:
        404: Task not found
    """
    try:
        # Check if task exists first
        task_result = celery_app.AsyncResult(task_id)
        if not task_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )

        logger.info(f"Starting SSE stream for task: {task_id}")
        
        async def task_status_generator() -> AsyncGenerator[str, None]:
            """Generate SSE events for task status updates."""
            import asyncio
            
            status_manager = SimpleStatusManager()
            previous_status = None
            
            while True:
                try:
                    current_status = await status_manager.get_unified_status(task_id)
                    
                    # 不再检查None，直接使用current_status
                    
                    # Only send updates when status changes
                    if current_status != previous_status:
                        if current_status.execution_status.value in ["completed", "failed"]:
                            # Send final status and close connection
                            event_type = "completed" if current_status.execution_status.value == "completed" else "failed"
                            event_data = {
                                "task_id": task_id,
                                "status": current_status.execution_status.value,
                                "progress": current_status.overall_progress,
                                "stage": current_status.current_stage
                            }
                            
                            if current_status.execution_status.value == "completed":
                                event_data.update({
                                    "literature_id": current_status.literature_id,
                                    "resource_url": current_status.resource_url
                                })
                            elif current_status.error_info:
                                event_data["error"] = current_status.error_info
                            
                            yield f"event: {event_type}\n"
                            yield f"data: {json.dumps(event_data)}\n\n"
                            break
                        else:
                            # Send progress update
                            event_data = {
                                "task_id": task_id,
                                "status": current_status.execution_status.value,
                                "progress": current_status.overall_progress,
                                "stage": current_status.current_stage
                            }
                            yield f"event: progress\n"
                            yield f"data: {json.dumps(event_data)}\n\n"
                        
                        previous_status = current_status
                    
                    # Wait before next poll
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"Error in SSE stream for task {task_id}: {e}")
                    yield f"event: error\n"
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break

        return StreamingResponse(
            task_status_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive", 
                "X-Accel-Buffering": "no",  # Nginx optimization
                "Access-Control-Allow-Origin": "*",  # CORS support
                "Access-Control-Allow-Headers": "Cache-Control",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up SSE stream for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}"
        ) from e


@router.delete("/{task_id}", summary="Cancel a task")
async def cancel_task(task_id: str) -> Dict[str, str]:
    """
    Cancel a running task.
    
    Attempts to cancel a task that is currently pending or in progress.
    Tasks that have already completed cannot be cancelled.
    
    Args:
        task_id: Unique identifier of the task to cancel
        
    Returns:
        Confirmation message with cancellation status
        
    Raises:
        404: Task not found
        400: Task cannot be cancelled (already completed/failed)
        500: Internal server error
    """
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        if not task_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {task_id}"
            )
        
        # Check if task can be cancelled
        if task_result.state in ["SUCCESS", "FAILURE"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task {task_id} has already {task_result.state.lower()} and cannot be cancelled"
            )
        
        # Attempt to revoke/cancel the task
        celery_app.control.revoke(task_id, terminate=True)
        
        logger.info(f"Task cancellation requested: {task_id}")
        return {
            "message": f"Task {task_id} cancellation requested",
            "task_id": task_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e!s}"
        ) from e
