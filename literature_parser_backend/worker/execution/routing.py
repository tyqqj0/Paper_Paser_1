"""
路由管理器

基于URL模式和配置决定处理器执行策略。
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Route:
    """路由定义"""
    name: str
    patterns: List[str]
    processors: List[str]
    priority: int = 1


class RouteManager:
    """路由管理器 - 决定URL使用哪些处理器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(RouteManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化内置路由规则（只初始化一次）"""
        if not RouteManager._initialized:
            self.routes = self._load_builtin_routes()
            RouteManager._initialized = True
    
    @classmethod
    def get_instance(cls):
        """获取单例实例的便捷方法"""
        return cls()
        
    def _load_builtin_routes(self) -> List[Route]:
        """加载内置路由规则 - 简化配置，直接在代码中定义"""
        return [
            Route(
                name="arxiv_fast_path",
                patterns=["arxiv.org/abs", "arxiv.org/pdf"],
                processors=["ArXiv Official API"],  # 🔧 使用ArXiv处理器，而不是Semantic Scholar
                priority=1
            ),
            Route(
                name="doi_fast_path", 
                patterns=["doi.org", "dx.doi.org"],
                processors=["CrossRef"],  # ✅ 修复名称
                priority=1
            ),
            Route(
                name="ieee_fast_path",
                patterns=["ieeexplore.ieee.org", "ieee.org", "computer.org"],
                processors=["Site Parser V2", "CrossRef", "Semantic Scholar"],  # IEEE优先使用站点解析
                priority=1
            ),
            Route(
                name="acm_fast_path", 
                patterns=["dl.acm.org", "acm.org"],
                processors=["Site Parser V2", "CrossRef", "Semantic Scholar"],  # ACM数字图书馆
                priority=1
            ),
            Route(
                name="springer_fast_path",
                patterns=["link.springer.com", "springer.com", "springerlink.com"],
                processors=["Site Parser V2", "CrossRef", "Semantic Scholar"],  # Springer
                priority=1
            ),
            Route(
                name="elsevier_fast_path",
                patterns=["sciencedirect.com", "elsevier.com"],
                processors=["Site Parser V2", "CrossRef", "Semantic Scholar"],  # ScienceDirect
                priority=1
            ),
            Route(
                name="neurips_enhanced_path",
                patterns=["proceedings.neurips.cc", "papers.nips.cc"],
                processors=["Site Parser V2", "ArXiv Official API", "CrossRef", "Semantic Scholar"],  # ✅ 优先使用ArXiv搜索，避免Semantic Scholar超时
                priority=2
            ),
            Route(
                name="conference_papers_path",
                patterns=["proceedings.mlr.press", "openaccess.thecvf.com", "aclanthology.org"],
                processors=["Site Parser V2", "CrossRef", "Semantic Scholar"],  # 会议论文网站
                priority=2
            ),
            Route(
                name="standard_waterfall",
                patterns=["*"],  # 通配符，匹配所有其他URL
                processors=["Semantic Scholar", "CrossRef", "Site Parser V2"],  # ✅ 修复所有名称
                priority=10  # 最低优先级
            )
        ]
    
    def determine_route(self, url: str, mapping_result: Optional[Dict] = None) -> Route:
        """
        根据URL和映射结果确定最佳路由
        
        Args:
            url: 输入URL
            mapping_result: URL映射服务的结果
            
        Returns:
            选中的路由
        """
        url_lower = url.lower()
        
        # 按优先级排序，优先匹配高优先级路由
        sorted_routes = sorted(self.routes, key=lambda r: r.priority)
        
        for route in sorted_routes:
            if self._matches_route(url_lower, route, mapping_result):
                logger.info(f"🎯 URL路由决策: {url} → {route.name} (处理器: {route.processors})")
                return route
                
        # 应该不会到这里，因为有通配符路由
        logger.warning(f"未找到匹配路由，使用默认路由: {url}")
        return self.routes[-1]  # 返回最后一个（通配符）路由
    
    def _matches_route(self, url: str, route: Route, mapping_result: Optional[Dict]) -> bool:
        """检查URL是否匹配路由模式"""
        
        # 检查URL模式匹配
        for pattern in route.patterns:
            if pattern == "*":
                return True  # 通配符匹配所有
            if pattern in url:
                return True
                
        # 检查特殊条件
        if mapping_result:
            # DOI检查
            if "doi" in route.name and mapping_result.get("doi"):
                return True
            # ArXiv检查    
            if "arxiv" in route.name and mapping_result.get("arxiv_id"):
                return True
                
        return False
    
    def is_fast_path(self, route: Route) -> bool:
        """判断是否为快速路径"""
        return "fast_path" in route.name
    
    def should_skip_dedup(self, route: Route) -> bool:
        """判断是否可以跳过复杂去重"""
        # 快速路径可以跳过复杂去重
        return self.is_fast_path(route)
