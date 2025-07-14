"""任务状态查询 API 端点"""

from datetime import datetime

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from loguru import logger

from literature_parser_backend.models.task import TaskStatus, TaskStatusDTO
from literature_parser_backend.worker.celery_app import celery_app

router = APIRouter(prefix="/task", tags=["任务管理"])


@router.get("/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str) -> TaskStatusDTO:
    """
    查询Celery任务的状态和结果

    Args:
        task_id: Celery任务ID

    Returns:
        TaskStatusDTO: 任务状态信息
    """
    try:
        # 获取任务结果
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
        response_data = {
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
                response_data["literature_id"] = result.get("literature_id")
                response_data["resource_url"] = (
                    f"/api/literature/{result.get('literature_id')}"
                    if result.get("literature_id")
                    else None
                )
            response_data["progress_percentage"] = 100

        elif task_result.status == "FAILURE":
            # 失败状态：提取错误信息
            error_msg = str(task_result.info) if task_result.info else "任务执行失败"
            response_data["error_info"] = {
                "error_type": "ProcessingError",
                "error_message": error_msg,
            }

        elif task_result.status == "PENDING":
            # 等待状态
            response_data["progress_percentage"] = 0

        elif task_result.status in ["STARTED", "RETRY"]:
            # 处理中状态：尝试获取进度信息
            if hasattr(task_result, "info") and isinstance(task_result.info, dict):
                info = task_result.info
                response_data["progress_percentage"] = info.get(
                    "progress_percentage", 50,
                )
            else:
                response_data["progress_percentage"] = 50

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
        logger.error(f"查询任务状态错误: {task_id} - {e!s}")

        # 如果是无效的任务ID，返回404
        if "Invalid task ID" in str(e) or "not found" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在",
            )

        # 其他错误返回500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询任务状态失败: {e!s}",
        )


@router.delete("/{task_id}", summary="取消任务")
async def cancel_task(task_id: str):
    """
    取消正在执行的任务

    Args:
        task_id: Celery任务ID

    Returns:
        取消操作结果
    """
    try:
        # 撤销任务
        celery_app.control.revoke(task_id, terminate=True)

        logger.info(f"任务已取消: {task_id}")
        return {"message": "任务取消成功", "task_id": task_id, "status": "cancelled"}

    except Exception as e:
        logger.error(f"取消任务错误: {task_id} - {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消任务失败: {e!s}",
        )
