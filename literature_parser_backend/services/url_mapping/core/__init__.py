"""
URL映射核心模块

包含核心基类和服务定义。
"""

from .base import URLAdapter, IdentifierStrategy
from .result import URLMappingResult
from .service import URLMappingService, get_url_mapping_service

__all__ = [
    "URLAdapter",
    "IdentifierStrategy", 
    "URLMappingResult",
    "URLMappingService",
    "get_url_mapping_service",
]
