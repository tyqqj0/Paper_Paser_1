"""
CVF适配器

处理CVPR、ICCV、ECCV等计算机视觉会议的URL映射。
"""

import re
import logging
from typing import List, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.regex_strategy import RegexStrategy

logger = logging.getLogger(__name__)


async def process_cvf_match(match: re.Match, result: URLMappingResult,
                          pattern_name: str, url: str, context: Dict[str, Any]):
    """处理CVF URL匹配结果"""
    paper_id = match.group(1)
    result.source_page_url = url
    result.venue = "CVF"
    result.confidence = 0.8
    result.identifiers["cvf_paper_id"] = paper_id
    
    # 尝试从URL中提取会议信息
    if "cvpr" in url.lower():
        result.venue = "CVPR"
    elif "iccv" in url.lower():
        result.venue = "ICCV"
    elif "eccv" in url.lower():
        result.venue = "ECCV"
    
    logger.debug(f"CVF匹配成功，论文ID: {paper_id}, 会议: {result.venue}")


class CVFAdapter(URLAdapter):
    """CVF适配器 - 处理CVPR、ICCV、ECCV等会议"""

    @property
    def name(self) -> str:
        return "cvf"

    @property
    def supported_domains(self) -> List[str]:
        return ["openaccess.thecvf.com", "thecvf.com"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册CVF支持的策略"""
        # CVF正则策略
        cvf_patterns = {
            "cvf_paper": r"openaccess\.thecvf\.com/content[^/]*/[^/]*/papers/([^/]+)\.html",
        }

        self.strategies = [
            RegexStrategy("cvf_regex", cvf_patterns, process_cvf_match, priority=1),
        ]

    def extract_paper_id(self, url: str) -> str:
        """从CVF URL中提取论文ID"""
        pattern = r"openaccess\.thecvf\.com/content[^/]*/[^/]*/papers/([^/]+)\.html"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None

    def extract_conference_info(self, url: str) -> Dict[str, str]:
        """从CVF URL中提取会议信息"""
        info = {}
        
        if "cvpr" in url.lower():
            info["conference"] = "CVPR"
        elif "iccv" in url.lower():
            info["conference"] = "ICCV"
        elif "eccv" in url.lower():
            info["conference"] = "ECCV"
        
        # 尝试提取年份
        year_match = re.search(r"(\d{4})", url)
        if year_match:
            info["year"] = year_match.group(1)
        
        return info
