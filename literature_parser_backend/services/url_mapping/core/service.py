"""
URL映射服务

提供URL到标识符映射的主要服务类。
"""

import asyncio
import logging
import requests
from typing import List, Optional, Dict, Any

from .base import URLAdapter
from .result import URLMappingResult

logger = logging.getLogger(__name__)


class URLMappingService:
    """URL映射服务主类"""

    def __init__(self, adapters: Optional[List[URLAdapter]] = None, enable_url_validation: bool = False):
        """
        初始化URL映射服务

        Args:
            adapters: 适配器列表，如果为None则使用默认适配器
            enable_url_validation: 是否启用URL有效性验证
        """
        self.adapters = adapters or []
        self.enable_url_validation = enable_url_validation
        if not self.adapters:
            self._register_default_adapters()

    def _register_default_adapters(self):
        """注册默认适配器"""
        try:
            # 导入适配器创建函数
            from ..adapters import create_all_adapters

            self.adapters = create_all_adapters()

            logger.info(f"注册了 {len(self.adapters)} 个默认适配器: {[a.name for a in self.adapters]}")
        except Exception as e:
            logger.error(f"注册默认适配器失败: {e}")
            # 作为备选方案，至少注册IEEE适配器
            try:
                from ..adapters.ieee import IEEEAdapter
                self.adapters = [IEEEAdapter()]
                logger.warning("使用备选方案，只注册了IEEE适配器")
            except Exception as fallback_error:
                logger.error(f"备选方案也失败: {fallback_error}")
                self.adapters = []

    def _validate_url(self, url: str, timeout: int = 10) -> bool:
        """
        验证URL是否可访问

        Args:
            url: 要验证的URL
            timeout: 超时时间（秒）

        Returns:
            URL是否可访问
        """
        try:
            logger.debug(f"验证URL可访问性: {url}")

            # 设置请求头，模拟浏览器访问
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }

            # 发送HEAD请求（更快，只获取响应头）
            response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)

            # 检查状态码
            if response.status_code == 200:
                logger.debug(f"✅ URL验证成功: {url}")
                return True
            elif response.status_code == 405:  # Method Not Allowed，尝试GET请求
                logger.debug(f"HEAD请求被拒绝，尝试GET请求: {url}")
                response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
                if response.status_code == 200:
                    logger.debug(f"✅ URL验证成功(GET): {url}")
                    return True

            logger.warning(f"❌ URL验证失败，状态码: {response.status_code}, URL: {url}")
            return False

        except requests.exceptions.Timeout:
            logger.warning(f"❌ URL验证超时: {url}")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"❌ URL连接失败: {url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"❌ URL验证请求异常: {e}, URL: {url}")
            return False
        except Exception as e:
            logger.error(f"❌ URL验证未知错误: {e}, URL: {url}")
            return False

    def _check_pdf_redirect(self, url: str) -> Optional[Dict[str, Any]]:
        """
        检查PDF重定向

        Args:
            url: 要检查的URL

        Returns:
            重定向信息字典，如果不需要重定向则返回None
        """
        try:
            from .pdf_redirector import get_pdf_redirector
            redirector = get_pdf_redirector()
            return redirector.check_redirect(url)
        except Exception as e:
            logger.warning(f"PDF重定向检查失败: {e}")
            return None

    async def map_url(self, url: str, enable_validation: bool = False, strict_validation: bool = False, skip_url_validation: bool = False) -> URLMappingResult:
        """
        将URL映射为标识符和相关信息（异步版本）

        Args:
            url: 要解析的URL
            enable_validation: 是否启用标识符验证
            strict_validation: 是否使用严格验证模式
            skip_url_validation: 是否跳过URL有效性验证

        Returns:
            URLMappingResult: 映射结果
        """
        logger.debug(f"开始映射URL: {url}")
        original_url = url

        # 1. 提前分离专门适配器和通用适配器（修复变量未定义bug）
        specialized_adapters = [a for a in self.adapters if a.name != "generic"]
        generic_adapters = [a for a in self.adapters if a.name == "generic"]

        # 2. PDF智能重定向检查
        redirect_info = self._check_pdf_redirect(url)
        if redirect_info:
            logger.info(f"🔄 PDF重定向: {url} → {redirect_info['canonical_url']}")
            logger.info(f"📝 重定向原因: {redirect_info['redirect_reason']}")
            url = redirect_info['canonical_url']  # 使用重定向后的URL继续处理

        # 3. URL有效性验证
        # 对于某些适配器（如ACM），我们可能希望直接从URL提取标识符，而不是进行HTTP验证
        # 检查适配器是否有优先的 extract_identifier_from_url 方法
        for adapter in specialized_adapters + generic_adapters:
            if adapter.can_handle(url) and hasattr(adapter, 'extract_identifier_from_url'):
                logger.debug(f"尝试使用适配器 {adapter.name} 的 extract_identifier_from_url 方法")
                direct_extraction_result = await adapter.extract_identifier_from_url(url)
                if direct_extraction_result and direct_extraction_result.is_successful():
                    logger.info(f"✅ 成功通过 {adapter.name} 直接从URL提取标识符")
                    if redirect_info:
                        direct_extraction_result.original_url = original_url
                        direct_extraction_result.canonical_url = redirect_info['canonical_url']
                        direct_extraction_result.redirect_reason = redirect_info['redirect_reason']
                    return direct_extraction_result
                else:
                    logger.debug(f"适配器 {adapter.name} 未能直接从URL提取标识符或提取失败")

        if self.enable_url_validation and not skip_url_validation:
            logger.info(f"🔍 验证URL有效性: {url}")
            if not self._validate_url(url):
                logger.warning(f"❌ URL验证失败，返回空结果: {url}")
                result = URLMappingResult()
                result.metadata['url_validation_failed'] = True
                result.metadata['error'] = f"URL {url} 无法访问或不存在"
                # 如果有重定向信息，也要记录
                if redirect_info:
                    result.original_url = original_url
                    result.canonical_url = redirect_info['canonical_url']
                    result.redirect_reason = redirect_info['redirect_reason']
                return result
            else:
                logger.info(f"✅ URL验证通过: {url}")

        # 4. 首先尝试专门适配器
        for adapter in specialized_adapters:
            if adapter.can_handle(url):
                logger.debug(f"使用专门适配器 {adapter.name} 处理URL")
                try:
                    result = await adapter.extract_identifiers(url, enable_validation, strict_validation)

                    if result and result.is_successful():
                        # 如果有重定向信息，添加到结果中
                        if redirect_info:
                            result.original_url = original_url
                            result.canonical_url = redirect_info['canonical_url']
                            result.redirect_reason = redirect_info['redirect_reason']

                        logger.info(f"成功映射URL: {url} -> DOI:{result.doi}, ArXiv:{result.arxiv_id}, Venue:{result.venue}, 策略:{result.strategy_used}")
                        if redirect_info:
                            logger.info(f"🔄 包含重定向信息: {original_url} → {redirect_info['canonical_url']}")
                        return result
                    else:
                        logger.debug(f"适配器 {adapter.name} 未找到有效标识符或有用信息")
                except Exception as e:
                    # 导入自定义异常类型
                    try:
                        from ....worker.execution.exceptions import URLNotFoundException, URLAccessFailedException, ParsingFailedException
                        # 如果是特定的错误类型，应该向上传递而不是继续尝试其他适配器
                        if isinstance(e, (URLNotFoundException, URLAccessFailedException, ParsingFailedException)):
                            logger.error(f"适配器 {adapter.name} 遇到特定错误，向上传递: {e}")
                            raise e
                    except ImportError:
                        # 如果无法导入异常类型，继续原有逻辑
                        pass
                    
                    logger.warning(f"适配器 {adapter.name} 处理URL失败: {e}")
                    continue

        # 5. 如果专门适配器都失败，尝试通用适配器作为备选方案
        if generic_adapters:
            logger.debug(f"专门适配器都失败，尝试通用备选方案")
            for adapter in generic_adapters:
                logger.debug(f"使用通用适配器 {adapter.name} 处理URL")
                try:
                    result = await adapter.extract_identifiers(url, enable_validation, strict_validation)

                    if result and result.is_successful():
                        # 如果有重定向信息，添加到结果中
                        if redirect_info:
                            result.original_url = original_url
                            result.canonical_url = redirect_info['canonical_url']
                            result.redirect_reason = redirect_info['redirect_reason']

                        logger.info(f"通用适配器成功映射URL: {url} -> DOI:{result.doi}, ArXiv:{result.arxiv_id}, Venue:{result.venue}, 策略:{result.strategy_used}")
                        if redirect_info:
                            logger.info(f"🔄 包含重定向信息: {original_url} → {redirect_info['canonical_url']}")
                        return result
                    else:
                        logger.debug(f"通用适配器 {adapter.name} 未找到有效标识符或有用信息")
                except Exception as e:
                    # 导入自定义异常类型
                    try:
                        from ....worker.execution.exceptions import URLNotFoundException, URLAccessFailedException, ParsingFailedException
                        # 如果是特定的错误类型，应该向上传递而不是继续尝试其他适配器
                        if isinstance(e, (URLNotFoundException, URLAccessFailedException, ParsingFailedException)):
                            logger.error(f"通用适配器 {adapter.name} 遇到特定错误，向上传递: {e}")
                            raise e
                    except ImportError:
                        # 如果无法导入异常类型，继续原有逻辑
                        pass
                    
                    logger.warning(f"通用适配器 {adapter.name} 处理URL失败: {e}")
                    continue

        # 6. 如果所有适配器都失败，返回空结果（但保留重定向信息）
        logger.debug(f"所有适配器都无法处理URL: {url}")
        result = URLMappingResult()
        if redirect_info:
            result.original_url = original_url
            result.canonical_url = redirect_info['canonical_url']
            result.redirect_reason = redirect_info['redirect_reason']
            logger.debug(f"返回空结果但保留重定向信息: {original_url} → {redirect_info['canonical_url']}")
        return result

    def map_url_sync(self, url: str) -> URLMappingResult:
        """
        将URL映射为标识符和相关信息（同步版本）

        Args:
            url: 要解析的URL

        Returns:
            URLMappingResult: 映射结果
        """
        try:
            # 检查是否已经有运行中的事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果有运行中的事件循环，使用线程池执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_async_in_new_loop, url)
                    return future.result()
            except RuntimeError:
                # 没有运行中的事件循环，可以安全使用run_until_complete
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.map_url(url))
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"同步URL映射失败: {e}")
            return URLMappingResult()

    def _run_async_in_new_loop(self, url: str) -> URLMappingResult:
        """在新的事件循环中运行异步方法"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.map_url(url))
        finally:
            loop.close()

    def map_url_with_validation(self, url: str, strict: bool = False) -> URLMappingResult:
        """
        带验证的URL映射（同步版本）

        Args:
            url: 要解析的URL
            strict: 是否使用严格验证模式（验证失败时不返回结果）

        Returns:
            URLMappingResult: 映射结果
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self.map_url(url, enable_validation=True, strict_validation=strict))
        except Exception as e:
            logger.error(f"带验证的URL映射失败: {e}")
            return URLMappingResult()

    def map_url_with_url_validation(self, url: str) -> URLMappingResult:
        """
        带URL有效性验证的映射（同步版本）

        Args:
            url: 要解析的URL

        Returns:
            URLMappingResult: 映射结果
        """
        # 临时启用URL验证
        original_validation = self.enable_url_validation
        self.enable_url_validation = True

        try:
            result = self.map_url_sync(url)
            return result
        finally:
            # 恢复原始设置
            self.enable_url_validation = original_validation

    def validate_url_only(self, url: str) -> bool:
        """
        仅验证URL是否可访问（不进行映射）

        Args:
            url: 要验证的URL

        Returns:
            URL是否可访问
        """
        return self._validate_url(url)

    def add_adapter(self, adapter: URLAdapter):
        """
        添加新的适配器
        
        Args:
            adapter: 要添加的适配器
        """
        self.adapters.append(adapter)
        logger.info(f"添加适配器: {adapter.name}")

    def remove_adapter(self, adapter_name: str):
        """
        移除适配器
        
        Args:
            adapter_name: 要移除的适配器名称
        """
        self.adapters = [a for a in self.adapters if a.name != adapter_name]
        logger.info(f"移除适配器: {adapter_name}")

    def get_supported_domains(self) -> dict:
        """
        获取所有支持的域名
        
        Returns:
            适配器名称到支持域名列表的映射
        """
        domains = {}
        for adapter in self.adapters:
            domains[adapter.name] = adapter.supported_domains
        return domains

    def get_adapter_by_name(self, name: str) -> Optional[URLAdapter]:
        """
        根据名称获取适配器
        
        Args:
            name: 适配器名称
            
        Returns:
            找到的适配器，如果没有找到则返回None
        """
        for adapter in self.adapters:
            if adapter.name == name:
                return adapter
        return None

    def get_adapters_for_url(self, url: str) -> List[URLAdapter]:
        """
        获取能处理指定URL的所有适配器
        
        Args:
            url: 要检查的URL
            
        Returns:
            能处理该URL的适配器列表
        """
        return [adapter for adapter in self.adapters if adapter.can_handle(url)]

    def health_check(self) -> dict:
        """
        健康检查
        
        Returns:
            服务状态信息
        """
        return {
            "service": "URLMappingService",
            "status": "healthy",
            "adapters_count": len(self.adapters),
            "adapters": [
                {
                    "name": adapter.name,
                    "supported_domains": adapter.supported_domains,
                    "strategies_count": len(adapter.strategies),
                }
                for adapter in self.adapters
            ]
        }


# 全局服务实例
_url_mapping_service = None


def get_url_mapping_service(enable_url_validation: bool = False) -> URLMappingService:
    """
    获取URL映射服务的单例实例

    Args:
        enable_url_validation: 是否启用URL验证（默认启用）

    Returns:
        URLMappingService实例
    """
    global _url_mapping_service
    if _url_mapping_service is None:
        _url_mapping_service = URLMappingService(enable_url_validation=enable_url_validation)
        logger.info(f"创建URL映射服务单例实例，URL验证: {'启用' if enable_url_validation else '禁用'}")
    return _url_mapping_service


def reset_url_mapping_service():
    """重置URL映射服务单例（主要用于测试）"""
    global _url_mapping_service
    _url_mapping_service = None
    logger.info("重置URL映射服务单例")
