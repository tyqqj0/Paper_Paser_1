#!/usr/bin/env python3
"""
元数据处理器模块初始化 - Paper Parser 0.2

自动导入所有处理器以触发注册机制，确保系统启动时
所有处理器都已注册到全局注册表中。
"""

import logging

logger = logging.getLogger(__name__)

# 自动导入所有处理器，触发自动注册
try:
    logger.debug("正在自动注册元数据处理器...")
    
    # 导入CrossRef处理器
    from . import crossref
    logger.debug("✅ CrossRef处理器已注册")
    
    # 导入Semantic Scholar处理器  
    from . import semantic_scholar
    logger.debug("✅ Semantic Scholar处理器已注册")
    
    # 导入ArXiv处理器
    from . import arxiv
    logger.debug("✅ ArXiv处理器已注册")
    
    # 导入网站解析处理器
    from . import site_parser
    logger.debug("✅ 网站解析处理器已注册")
    
    # 导入GROBID处理器
    # from . import grobid
    # logger.debug("✅ GROBID处理器已注册")
    
    logger.info("✅ 所有元数据处理器自动注册完成")
    
except Exception as e:
    logger.error(f"❌ 处理器自动注册失败: {e}")

# 提供便捷的访问接口
from ..registry import get_global_registry

def get_all_processors():
    """获取所有已注册的处理器列表"""
    registry = get_global_registry()
    return registry.list_processors()

def get_available_processors(identifiers_data, settings=None):
    """获取可以处理指定标识符的处理器列表"""
    registry = get_global_registry()
    return registry.get_available_processors(identifiers_data, settings=settings)

__all__ = [
    'get_all_processors',
    'get_available_processors'
]