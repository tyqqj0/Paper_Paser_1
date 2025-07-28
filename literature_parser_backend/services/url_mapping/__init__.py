"""
URL映射服务模块

提供学术文献URL到标识符的映射功能，支持多种期刊和数据库。

主要组件:
- URLMappingService: 主服务类
- URLAdapter: 适配器基类
- URLMappingResult: 结果模型

使用示例:
    from literature_parser_backend.services.url_mapping import get_url_mapping_service
    
    service = get_url_mapping_service()
    result = service.map_url_sync("https://arxiv.org/abs/2301.00001")
    print(result.arxiv_id)  # 输出: 2301.00001
"""

from .core.service import URLMappingService, get_url_mapping_service
from .core.result import URLMappingResult
from .core.base import URLAdapter, IdentifierStrategy

__all__ = [
    "URLMappingService",
    "get_url_mapping_service", 
    "URLMappingResult",
    "URLAdapter",
    "IdentifierStrategy",
]

__version__ = "1.0.0"
