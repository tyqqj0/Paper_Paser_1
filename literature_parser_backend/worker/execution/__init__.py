"""
智能执行器模块

提供基于路由的智能处理器执行系统，自动判断并行执行和Hook触发。
"""

from .smart_router import SmartRouter
from .routing import RouteManager
from .data_pipeline import DataPipeline

__all__ = ["SmartRouter", "RouteManager", "DataPipeline"]
