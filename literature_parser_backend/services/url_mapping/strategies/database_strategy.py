"""
数据库查询策略

通过查询第三方数据库来获取标识符的策略。
"""

import logging
from typing import Dict, Optional, Any, Callable

from ..core.base import IdentifierStrategy
from ..core.result import URLMappingResult

logger = logging.getLogger(__name__)


class DatabaseStrategy(IdentifierStrategy):
    """基于第三方数据库的标识符提取策略"""

    def __init__(self, name: str, database_func: Optional[Callable] = None, priority: int = 4):
        """
        初始化数据库查询策略
        
        Args:
            name: 策略名称
            database_func: 数据库查询函数
            priority: 优先级
        """
        self._name = name
        self.database_func = database_func
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """通过第三方数据库查询提取标识符"""
        try:
            logger.debug(f"开始数据库查询策略: {self.name}")
            
            if self.database_func:
                result = await self.database_func(url, context)
            else:
                result = await self._default_database_query(url, context)
            
            if result and result.is_successful():
                logger.info(f"数据库查询策略 {self.name} 成功获取信息")
                return result
            else:
                logger.debug(f"数据库查询策略 {self.name} 未找到有效信息")
                return None
                
        except Exception as e:
            logger.warning(f"数据库查询策略 {self.name} 执行失败: {e}")
            return None

    async def _default_database_query(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """
        默认数据库查询实现
        
        子类可以重写，或者通过database_func自定义
        """
        logger.debug("使用默认数据库查询实现（空实现）")
        return None

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断策略是否可以处理该URL
        
        数据库查询策略通常需要网络访问和API密钥
        """
        # 基本检查：确保URL是HTTP/HTTPS
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
        
        # 可以添加更多检查，比如API密钥是否可用、网络连接状态等
        return True

    def set_database_function(self, database_func: Callable):
        """
        设置新的数据库查询函数
        
        Args:
            database_func: 新的数据库查询函数
        """
        self.database_func = database_func
        logger.debug(f"更新数据库查询函数: {self.name}")

    def get_database_function(self) -> Optional[Callable]:
        """
        获取当前的数据库查询函数
        
        Returns:
            当前的数据库查询函数
        """
        return self.database_func
