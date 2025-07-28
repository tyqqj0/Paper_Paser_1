"""
API调用策略

通过调用外部API来获取标识符的策略。
"""

import logging
from typing import Dict, Optional, Any, Callable

from ..core.base import IdentifierStrategy
from ..core.result import URLMappingResult

logger = logging.getLogger(__name__)


class APIStrategy(IdentifierStrategy):
    """基于API调用的标识符提取策略"""

    def __init__(self, name: str, api_func: Optional[Callable] = None, priority: int = 3):
        """
        初始化API调用策略
        
        Args:
            name: 策略名称
            api_func: API调用函数
            priority: 优先级
        """
        self._name = name
        self.api_func = api_func
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """通过API调用提取标识符"""
        try:
            logger.debug(f"开始API调用策略: {self.name}")
            
            if self.api_func:
                result = await self.api_func(url, context)
            else:
                result = await self._default_api_call(url, context)
            
            if result and result.is_successful():
                logger.info(f"API调用策略 {self.name} 成功获取信息")
                return result
            else:
                logger.debug(f"API调用策略 {self.name} 未找到有效信息")
                return None
                
        except Exception as e:
            logger.warning(f"API调用策略 {self.name} 执行失败: {e}")
            return None

    async def _default_api_call(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """
        默认API调用实现
        
        子类可以重写，或者通过api_func自定义
        """
        logger.debug("使用默认API调用实现（空实现）")
        return None

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断策略是否可以处理该URL
        
        API调用策略通常需要网络访问和API密钥
        """
        # 基本检查：确保URL是HTTP/HTTPS
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
        
        # 可以添加更多检查，比如API密钥是否可用、速率限制等
        return True

    def set_api_function(self, api_func: Callable):
        """
        设置新的API调用函数
        
        Args:
            api_func: 新的API调用函数
        """
        self.api_func = api_func
        logger.debug(f"更新API调用函数: {self.name}")

    def get_api_function(self) -> Optional[Callable]:
        """
        获取当前的API调用函数
        
        Returns:
            当前的API调用函数
        """
        return self.api_func
