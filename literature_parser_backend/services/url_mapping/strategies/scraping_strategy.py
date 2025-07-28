"""
页面解析策略

通过抓取和解析网页内容来提取标识符的策略。
"""

import logging
from typing import Dict, Optional, Any, Callable

from ..core.base import IdentifierStrategy
from ..core.result import URLMappingResult

logger = logging.getLogger(__name__)


class ScrapingStrategy(IdentifierStrategy):
    """基于页面解析的标识符提取策略"""

    def __init__(self, name: str, scraping_func: Callable, priority: int = 2):
        """
        初始化页面解析策略
        
        Args:
            name: 策略名称
            scraping_func: 页面解析函数
            priority: 优先级
        """
        self._name = name
        self.scraping_func = scraping_func
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """通过页面解析提取标识符"""
        try:
            logger.debug(f"开始页面解析策略: {self.name}")
            
            # 调用页面解析函数
            result = await self.scraping_func(url, context)
            
            if result and result.is_successful():
                logger.info(f"页面解析策略 {self.name} 成功提取信息")
                return result
            else:
                logger.debug(f"页面解析策略 {self.name} 未找到有效信息")
                return None
                
        except Exception as e:
            logger.warning(f"页面解析策略 {self.name} 执行失败: {e}")
            return None

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断策略是否可以处理该URL
        
        页面解析策略通常需要网络访问，可以在这里添加额外的检查
        """
        # 基本检查：确保URL是HTTP/HTTPS
        if not (url.startswith('http://') or url.startswith('https://')):
            return False
        
        # 可以添加更多检查，比如域名白名单、网络连接状态等
        return True

    def set_scraping_function(self, scraping_func: Callable):
        """
        设置新的页面解析函数
        
        Args:
            scraping_func: 新的页面解析函数
        """
        self.scraping_func = scraping_func
        logger.debug(f"更新页面解析函数: {self.name}")

    def get_scraping_function(self) -> Callable:
        """
        获取当前的页面解析函数
        
        Returns:
            当前的页面解析函数
        """
        return self.scraping_func
