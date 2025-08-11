"""
Semantic Scholar适配器

专门处理Semantic Scholar URL，避免URL验证问题，
直接从URL中提取paper ID并通过API获取元数据。
"""

import re
import logging
from typing import List, Optional, Dict, Any

from ..core.base import URLAdapter
from ..core.result import URLMappingResult
from ..strategies.database_strategy import DatabaseStrategy

logger = logging.getLogger(__name__)


async def semantic_scholar_paper_id_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """
    从Semantic Scholar URL中提取paper ID并通过API获取元数据
    
    支持的URL格式：
    - https://www.semanticscholar.org/paper/{title}/{paper_id}
    - https://www.semanticscholar.org/paper/{paper_id}
    """
    try:
        logger.info(f"🔍 处理Semantic Scholar URL: {url}")
        
        # 提取paper ID的正则表达式
        patterns = [
            r'semanticscholar\.org/paper/[^/]+/([a-f0-9]{40})',  # 带标题的格式
            r'semanticscholar\.org/paper/([a-f0-9]{40})',       # 直接paper ID格式
        ]
        
        paper_id = None
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                paper_id = match.group(1)
                break
        
        if not paper_id:
            logger.debug(f"无法从URL提取Semantic Scholar paper ID: {url}")
            return None
        
        logger.info(f"✅ 提取到Semantic Scholar paper ID: {paper_id}")
        
        # 通过Semantic Scholar API获取论文信息
        from ....services.semantic_scholar import SemanticScholarClient

        client = SemanticScholarClient()
        paper_data = client.get_metadata(paper_id, id_type="paper_id")
        
        if not paper_data:
            logger.warning(f"Semantic Scholar API未找到论文: {paper_id}")
            return None
        
        # 构建结果
        result = URLMappingResult()
        result.source_page_url = url
        
        # 提取DOI
        external_ids = paper_data.get('externalIds', {})
        if external_ids.get('DOI'):
            result.doi = external_ids['DOI']
            logger.info(f"✅ 从Semantic Scholar获取到DOI: {result.doi}")
        
        # 提取ArXiv ID
        if external_ids.get('ArXiv'):
            result.arxiv_id = external_ids['ArXiv']
            logger.info(f"✅ 从Semantic Scholar获取到ArXiv ID: {result.arxiv_id}")
        
        # 提取其他信息
        if paper_data.get('title'):
            result.title = paper_data['title']
        
        if paper_data.get('venue'):
            result.venue = paper_data['venue']
        
        if paper_data.get('year'):
            result.year = paper_data['year']
        
        # 提取PDF URL
        open_access_pdf = paper_data.get('openAccessPdf')
        if open_access_pdf and open_access_pdf.get('url'):
            result.pdf_url = open_access_pdf['url']
        
        # 添加元数据
        result.metadata.update({
            'semantic_scholar_id': paper_id,
            'citation_count': paper_data.get('citationCount'),
            'reference_count': paper_data.get('referenceCount'),
            'influential_citation_count': paper_data.get('influentialCitationCount'),
            'is_open_access': paper_data.get('isOpenAccess'),
            'fields_of_study': paper_data.get('fieldsOfStudy', []),
        })
        
        logger.info(f"✅ 成功处理Semantic Scholar论文: {paper_data.get('title', 'Unknown')}")
        return result
        
    except Exception as e:
        logger.error(f"Semantic Scholar处理失败: {e}")
        return None


class SemanticScholarAdapter(URLAdapter):
    """Semantic Scholar适配器"""
    
    @property
    def name(self) -> str:
        return "semantic_scholar"
    
    @property
    def supported_domains(self) -> List[str]:
        return ["semanticscholar.org", "www.semanticscholar.org"]
    
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理该URL"""
        return any(domain in url.lower() for domain in self.supported_domains)
    
    def _register_strategies(self):
        """注册Semantic Scholar支持的策略"""
        self.strategies = [
            # 策略1: 通过paper ID获取论文信息（优先级最高）
            DatabaseStrategy(
                "semantic_scholar_paper_id", 
                semantic_scholar_paper_id_func, 
                priority=1
            ),
        ]
    
    def _get_context(self) -> Dict[str, Any]:
        """获取适配器上下文"""
        return {
            "adapter_name": self.name,
            "supported_domains": self.supported_domains,
            "skip_url_validation": True,  # 跳过URL验证，因为Semantic Scholar有反爬虫保护
        }
