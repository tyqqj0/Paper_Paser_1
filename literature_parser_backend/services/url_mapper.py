"""
URL映射服务 - 统一处理各种学术网站的URL解析和转换

支持的网站类型：
- ArXiv (abs, pdf, html)
- CVF (CVPR, ICCV, ECCV等)
- NeurIPS
- Nature
- IEEE
- 其他学术网站

架构特点：
- 策略模式：每个平台支持多种获取策略
- 瀑布流：按优先级尝试不同策略
- 解耦设计：策略独立，易于扩展和测试
"""

import re
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class URLMappingResult:
    """URL映射结果"""
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pdf_url: Optional[str] = None
    source_page_url: Optional[str] = None
    venue: Optional[str] = None  # 会议/期刊名称
    year: Optional[int] = None
    confidence: float = 1.0  # 置信度 0-1
    source_adapter: Optional[str] = None  # 使用的适配器名称
    strategy_used: Optional[str] = None  # 使用的策略名称


class IdentifierStrategy(ABC):
    """标识符提取策略接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级，数字越小优先级越高"""
        pass

    @abstractmethod
    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """
        从URL提取标识符

        Args:
            url: 要解析的URL
            context: 上下文信息，包含平台特定的配置和状态

        Returns:
            URLMappingResult或None
        """
        pass

    def can_handle(self, url: str, context: Dict[str, Any]) -> bool:
        """
        判断策略是否可以处理该URL
        默认返回True，子类可以重写以添加特定条件
        """
        return True


class URLAdapter(ABC):
    """URL适配器基类 - 支持多策略的增强版本"""

    def __init__(self):
        self.strategies: List[IdentifierStrategy] = []
        self._register_strategies()

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器名称"""
        pass

    @property
    @abstractmethod
    def supported_domains(self) -> List[str]:
        """支持的域名列表"""
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断是否能处理该URL"""
        pass

    @abstractmethod
    def _register_strategies(self):
        """注册该平台支持的策略"""
        pass

    def _get_context(self) -> Dict[str, Any]:
        """获取平台特定的上下文信息"""
        return {
            "adapter_name": self.name,
            "supported_domains": self.supported_domains,
        }

    async def extract_identifiers(self, url: str) -> URLMappingResult:
        """
        使用多策略瀑布流提取标识符
        按优先级尝试各种策略，直到成功或全部失败
        """
        logger.debug(f"开始使用 {self.name} 适配器处理URL: {url}")

        context = self._get_context()
        available_strategies = [
            s for s in self.strategies
            if s.can_handle(url, context)
        ]

        if not available_strategies:
            logger.warning(f"没有可用的策略处理URL: {url}")
            return URLMappingResult(source_adapter=self.name)

        # 按优先级排序并尝试每个策略
        best_result = None

        for strategy in sorted(available_strategies, key=lambda s: s.priority):
            try:
                logger.debug(f"尝试策略: {strategy.name} (优先级: {strategy.priority})")
                result = await strategy.extract_identifiers(url, context)

                if result:
                    # 检查是否有有效的标识符或有用信息
                    has_identifiers = bool(result.doi or result.arxiv_id)
                    has_useful_info = bool(result.venue or result.source_page_url or result.pdf_url)

                    if has_identifiers or has_useful_info:
                        result.source_adapter = self.name
                        result.strategy_used = strategy.name

                        # 如果有标识符（DOI/ArXiv），立即返回
                        if has_identifiers:
                            logger.info(f"策略 {strategy.name} 成功提取标识符: DOI={result.doi}, ArXiv={result.arxiv_id}")
                            return result

                        # 如果只有有用信息，保存为备选结果，继续尝试其他策略
                        if not best_result:
                            best_result = result
                            logger.debug(f"策略 {strategy.name} 提取到有用信息，继续尝试获取标识符")
                    else:
                        logger.debug(f"策略 {strategy.name} 未找到有效标识符或有用信息")
                else:
                    logger.debug(f"策略 {strategy.name} 返回None")

            except Exception as e:
                logger.warning(f"策略 {strategy.name} 执行失败: {e}")
                continue

        # 如果没有找到标识符，返回最好的结果（如果有的话）
        if best_result:
            logger.info(f"返回最佳结果: Venue={best_result.venue}, Strategy={best_result.strategy_used}")
            return best_result

        logger.info(f"所有策略都失败，返回空结果")
        return URLMappingResult(source_adapter=self.name)


# ===============================================
# 通用策略实现
# ===============================================

class RegexStrategy(IdentifierStrategy):
    """基于正则表达式的标识符提取策略"""

    def __init__(self, name: str, patterns: Dict[str, str], processor_func=None, priority: int = 1):
        self._name = name
        self.patterns = patterns
        self.processor_func = processor_func  # 自定义处理函数
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """使用正则表达式提取标识符"""
        result = URLMappingResult()

        for pattern_name, pattern in self.patterns.items():
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                logger.debug(f"正则模式 {pattern_name} 匹配成功")

                # 使用自定义处理函数或默认处理
                if self.processor_func:
                    await self.processor_func(match, result, pattern_name, url, context)
                else:
                    await self._default_process_match(match, result, pattern_name, url, context)
                break

        # 返回结果的条件：有标识符或有其他有用信息
        has_identifiers = bool(result.doi or result.arxiv_id)
        has_useful_info = bool(result.venue or result.source_page_url or result.pdf_url)

        return result if (has_identifiers or has_useful_info) else None

    async def _default_process_match(self, match: re.Match, result: URLMappingResult,
                                   pattern_name: str, url: str, context: Dict[str, Any]):
        """默认的匹配处理逻辑"""
        # 子类可以重写，或者通过processor_func自定义
        pass


class APIStrategy(IdentifierStrategy):
    """基于API查询的标识符提取策略"""

    def __init__(self, name: str, api_func=None, priority: int = 2):
        self._name = name
        self.api_func = api_func  # 自定义API查询函数
        self._priority = priority

    @property
    def name(self) -> str:
        return self._name

    @property
    def priority(self) -> int:
        return self._priority

    async def extract_identifiers(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """通过API查询提取标识符"""
        if self.api_func:
            return await self.api_func(url, context)
        else:
            return await self._default_query_api(url, context)

    async def _default_query_api(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """默认API查询实现"""
        # 子类可以重写，或者通过api_func自定义
        return None


class ScrapingStrategy(IdentifierStrategy):
    """基于页面解析的标识符提取策略"""

    def __init__(self, name: str, scraping_func=None, priority: int = 3):
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
        if self.scraping_func:
            return await self.scraping_func(url, context)
        else:
            return await self._default_scraping(url, context)

    async def _default_scraping(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """默认页面解析实现"""
        # 子类可以重写，或者通过scraping_func自定义
        return None


class DatabaseStrategy(IdentifierStrategy):
    """基于第三方数据库的标识符提取策略"""

    def __init__(self, name: str, database_func=None, priority: int = 4):
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
        if self.database_func:
            return await self.database_func(url, context)
        else:
            return await self._default_database_query(url, context)

    async def _default_database_query(self, url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
        """默认数据库查询实现"""
        # 子类可以重写，或者通过database_func自定义
        return None


# ===============================================
# 平台特定的处理函数
# ===============================================

async def process_arxiv_match(match: re.Match, result: URLMappingResult,
                            pattern_name: str, url: str, context: Dict[str, Any]):
    """处理ArXiv ID匹配结果"""
    arxiv_id = match.group(1)
    result.arxiv_id = arxiv_id

    # 生成标准URL
    result.source_page_url = f"https://arxiv.org/abs/{arxiv_id}"
    result.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # 从ArXiv ID推断年份
    if re.match(r"\d{4}\.\d{4,5}", arxiv_id):
        year_str = arxiv_id[:2]
        # ArXiv从1991年开始，07年后使用4位年份
        if int(year_str) >= 7:
            result.year = 2000 + int(year_str)
        else:
            result.year = 2000 + int(year_str)

    result.confidence = 0.95


async def process_ieee_match(match: re.Match, result: URLMappingResult,
                           pattern_name: str, url: str, context: Dict[str, Any]):
    """处理IEEE文档ID匹配结果"""
    doc_id = match.group(1)
    result.source_page_url = url
    result.venue = "IEEE"

    # 不生成虚假DOI！
    # IEEE文档ID无法直接转换为DOI，需要通过其他策略获取真实DOI
    # 只设置基础信息，DOI留给后续的API策略或页面解析策略获取
    result.confidence = 0.8  # 提高置信度，因为我们确实识别了IEEE文档


async def process_nature_match(match: re.Match, result: URLMappingResult,
                             pattern_name: str, url: str, context: Dict[str, Any]):
    """处理Nature文章ID匹配结果"""
    article_id = match.group(1)
    result.source_page_url = url
    result.venue = "Nature"

    # 如果是DOI格式的文章ID，直接使用
    if article_id.startswith("s") or "nature" in article_id:
        result.doi = f"10.1038/{article_id}"
        result.confidence = 0.9


async def process_cvf_match(match: re.Match, result: URLMappingResult,
                          pattern_name: str, url: str, context: Dict[str, Any]):
    """处理CVF URL匹配结果"""
    venue_year = match.group(1)  # 如: cvf_2017, ICCV_2019

    # 解析会议和年份
    venue_match = re.match(r"([a-z]+)_(\d{4})", venue_year, re.IGNORECASE)
    if venue_match:
        venue = venue_match.group(1).upper()
        year = int(venue_match.group(2))

        result.venue = venue
        result.year = year
        result.pdf_url = url
        result.confidence = 0.8

        # 尝试构建source page URL
        html_url = url.replace(".pdf", ".html")
        result.source_page_url = html_url


async def process_neurips_match(match: re.Match, result: URLMappingResult,
                              pattern_name: str, url: str, context: Dict[str, Any]):
    """处理NeurIPS URL匹配结果"""
    year = int(match.group(1))

    result.year = year
    result.venue = "NeurIPS"
    result.pdf_url = url if url.endswith(".pdf") else None
    result.source_page_url = url if url.endswith(".html") else None
    result.confidence = 0.8


class ArXivAdapter(URLAdapter):
    """ArXiv适配器 - 支持多策略的增强版本"""

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def supported_domains(self) -> List[str]:
        return ["arxiv.org"]

    def can_handle(self, url: str) -> bool:
        return "arxiv.org" in url.lower()

    def _register_strategies(self):
        """注册ArXiv支持的策略"""
        # ArXiv正则策略
        arxiv_patterns = {
            "new_format": r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?",
            "old_format": r"arxiv\.org/(?:abs|pdf|html)/([a-z-]+/\d{7})(?:v\d+)?(?:\.pdf)?",
        }

        self.strategies = [
            RegexStrategy("arxiv_regex", arxiv_patterns, process_arxiv_match, priority=1),
            # 未来可以添加更多策略：
            # APIStrategy("arxiv_api", arxiv_api_func, priority=2),
            # DatabaseStrategy("arxiv_semantic_scholar", semantic_scholar_func, priority=3),
        ]


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
            "cvf_paper": r"openaccess\.thecvf\.com/content_([^/]+)/papers/([^/]+)\.pdf",
        }

        self.strategies = [
            RegexStrategy("cvf_regex", cvf_patterns, process_cvf_match, priority=1),
            # 未来可以添加更多策略：
            # DatabaseStrategy("cvf_dblp", dblp_func, priority=2),
        ]


class NatureAdapter(URLAdapter):
    """Nature适配器 - 处理Nature系列期刊"""

    @property
    def name(self) -> str:
        return "nature"

    @property
    def supported_domains(self) -> List[str]:
        return ["nature.com", "www.nature.com"]

    def can_handle(self, url: str) -> bool:
        return "nature.com" in url.lower()

    def _register_strategies(self):
        """注册Nature支持的策略"""
        # Nature正则策略
        nature_patterns = {
            "article_id": r"nature\.com/articles/([^/?]+)",
        }

        self.strategies = [
            RegexStrategy("nature_regex", nature_patterns, process_nature_match, priority=1),
            # 未来可以添加更多策略：
            # APIStrategy("nature_api", nature_api_func, priority=2),
        ]


# IEEE特定的API函数
async def ieee_scraping_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """IEEE页面解析函数 - 提取真实DOI"""
    try:
        # 提取文档ID
        doc_id_match = re.search(r"document/(\d+)", url)
        if not doc_id_match:
            return None

        doc_id = doc_id_match.group(1)
        logger.info(f"尝试通过页面解析获取IEEE文档 {doc_id} 的真实DOI")

        # 导入requests模块
        import requests

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # 获取页面内容
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.warning(f"IEEE页面访问失败，状态码: {response.status_code}")
            return None

        content = response.text

        # 方法1: 查找meta标签中的DOI
        meta_pattern = r'<meta[^>]*name=["\']citation_doi["\'][^>]*content=["\']([^"\']+)["\']'
        meta_match = re.search(meta_pattern, content, re.IGNORECASE)
        if meta_match:
            doi = meta_match.group(1)
            logger.info(f"✅ 从meta标签找到DOI: {doi}")

            result = URLMappingResult()
            result.doi = doi
            result.source_page_url = url
            result.venue = "IEEE"
            result.confidence = 0.95  # 高置信度，因为是从官方页面提取的
            return result

        # 方法2: 查找DOI链接
        doi_link_pattern = r'https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s"\'<>]+)'
        doi_link_match = re.search(doi_link_pattern, content)
        if doi_link_match:
            doi = doi_link_match.group(1)
            logger.info(f"✅ 从DOI链接找到DOI: {doi}")

            result = URLMappingResult()
            result.doi = doi
            result.source_page_url = url
            result.venue = "IEEE"
            result.confidence = 0.9
            return result

        # 方法3: 直接搜索DOI模式
        doi_pattern = r'10\.\d{4,}/[A-Za-z0-9\.\-_/]+'
        matches = re.findall(doi_pattern, content)
        if matches:
            # 过滤掉明显不是DOI的结果
            valid_dois = [m for m in matches if len(m) > 10 and '/' in m and 'IEEE' not in m.upper()]
            if valid_dois:
                doi = valid_dois[0]
                logger.info(f"✅ 从正则表达式找到DOI: {doi}")

                result = URLMappingResult()
                result.doi = doi
                result.source_page_url = url
                result.venue = "IEEE"
                result.confidence = 0.85
                return result

        logger.info(f"❌ 未能从IEEE页面提取到DOI")
        return None

    except Exception as e:
        logger.warning(f"IEEE页面解析失败: {e}")
        return None


async def ieee_semantic_scholar_func(url: str, context: Dict[str, Any]) -> Optional[URLMappingResult]:
    """IEEE Semantic Scholar查询函数"""
    try:
        # 提取文档ID
        doc_id_match = re.search(r"document/(\d+)", url)
        if not doc_id_match:
            return None

        doc_id = doc_id_match.group(1)
        logger.info(f"尝试通过Semantic Scholar查询IEEE文档 {doc_id}")

        # TODO: 实现Semantic Scholar查询
        # 这里可以添加以下功能：
        # 1. 使用IEEE URL作为查询条件
        # 2. 调用Semantic Scholar API
        # 3. 从返回结果中提取真实DOI

        # 暂时返回None，表示此策略尚未实现
        logger.debug("IEEE Semantic Scholar查询策略尚未实现")
        return None

    except Exception as e:
        logger.warning(f"IEEE Semantic Scholar查询失败: {e}")
        return None


class IEEEAdapter(URLAdapter):
    """IEEE适配器 - 支持多策略的增强版本"""

    @property
    def name(self) -> str:
        return "ieee"

    @property
    def supported_domains(self) -> List[str]:
        return ["ieeexplore.ieee.org"]

    def can_handle(self, url: str) -> bool:
        return "ieeexplore.ieee.org" in url.lower()

    def _register_strategies(self):
        """注册IEEE支持的策略"""
        # IEEE正则策略
        ieee_patterns = {
            "document_id": r"ieeexplore\.ieee\.org/(?:document|abstract/document)/(\d+)",
        }

        self.strategies = [
            RegexStrategy("ieee_regex", ieee_patterns, process_ieee_match, priority=1),
            ScrapingStrategy("ieee_scraping", ieee_scraping_func, priority=2),
            DatabaseStrategy("ieee_semantic_scholar", ieee_semantic_scholar_func, priority=3),
            # 未来可以添加：
            # APIStrategy("ieee_api", ieee_api_func, priority=2),
            # DatabaseStrategy("ieee_crossref", crossref_func, priority=4),
        ]


class NeurIPSAdapter(URLAdapter):
    """NeurIPS适配器 - 处理NeurIPS会议论文"""

    @property
    def name(self) -> str:
        return "neurips"

    @property
    def supported_domains(self) -> List[str]:
        return ["proceedings.neurips.cc", "papers.nips.cc"]

    def can_handle(self, url: str) -> bool:
        return any(domain in url.lower() for domain in self.supported_domains)

    def _register_strategies(self):
        """注册NeurIPS支持的策略"""
        # NeurIPS正则策略
        neurips_patterns = {
            "neurips_paper": r"(?:proceedings\.neurips\.cc|papers\.nips\.cc)/paper/(\d{4})/(?:file|hash)/([^/]+)-(?:Paper\.pdf|Abstract\.html)",
        }

        self.strategies = [
            RegexStrategy("neurips_regex", neurips_patterns, process_neurips_match, priority=1),
            # 未来可以添加更多策略：
            # DatabaseStrategy("neurips_dblp", dblp_func, priority=2),
        ]


class URLMappingService:
    """URL映射服务主类"""

    def __init__(self):
        self.adapters: List[URLAdapter] = []
        self._register_default_adapters()

    def _register_default_adapters(self):
        """注册默认适配器"""
        self.adapters = [
            ArXivAdapter(),
            CVFAdapter(),
            NatureAdapter(),
            IEEEAdapter(),
            NeurIPSAdapter(),
        ]
    
    def register_adapter(self, adapter: URLAdapter):
        """注册新的适配器"""
        self.adapters.append(adapter)
        logger.info(f"注册URL适配器: {adapter.name}")
    
    async def map_url(self, url: str) -> URLMappingResult:
        """
        将URL映射为标识符和相关信息（异步版本，支持多策略）

        Args:
            url: 要解析的URL

        Returns:
            URLMappingResult: 映射结果
        """
        logger.debug(f"开始映射URL: {url}")

        # 尝试每个适配器
        for adapter in self.adapters:
            if adapter.can_handle(url):
                logger.debug(f"使用适配器 {adapter.name} 处理URL")
                try:
                    result = await adapter.extract_identifiers(url)
                    # 检查是否有有效的标识符或有用信息
                    has_identifiers = bool(result.doi or result.arxiv_id)
                    has_useful_info = bool(result.venue or result.source_page_url or result.pdf_url)

                    if has_identifiers or has_useful_info:
                        logger.info(f"成功映射URL: {url} -> DOI:{result.doi}, ArXiv:{result.arxiv_id}, Venue:{result.venue}, 策略:{result.strategy_used}")
                        return result
                    else:
                        logger.debug(f"适配器 {adapter.name} 未找到有效标识符或有用信息")
                except Exception as e:
                    logger.warning(f"适配器 {adapter.name} 处理URL失败: {e}")
                    continue

        # 如果没有适配器能处理，返回空结果
        logger.debug(f"没有适配器能处理URL: {url}")
        return URLMappingResult()

    def map_url_sync(self, url: str) -> URLMappingResult:
        """
        同步版本的URL映射（向后兼容）
        """
        try:
            # 创建新的事件循环或使用现有的
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中，创建新的任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.map_url(url))
                        return future.result()
                else:
                    return loop.run_until_complete(self.map_url(url))
            except RuntimeError:
                # 没有事件循环，创建新的
                return asyncio.run(self.map_url(url))
        except Exception as e:
            logger.error(f"同步URL映射失败: {e}")
            return URLMappingResult()
    
    def get_supported_domains(self) -> Dict[str, List[str]]:
        """获取所有支持的域名"""
        domains = {}
        for adapter in self.adapters:
            domains[adapter.name] = adapter.supported_domains
        return domains


# 全局服务实例
_url_mapping_service: Optional[URLMappingService] = None


def get_url_mapping_service() -> URLMappingService:
    """获取URL映射服务实例（单例模式）"""
    global _url_mapping_service
    if _url_mapping_service is None:
        _url_mapping_service = URLMappingService()
    return _url_mapping_service
