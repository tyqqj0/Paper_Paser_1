"""
智能路由器 - 纯粹的路由选择和Hook编排

只负责两件事：
1. 根据URL/标识符选择最优处理路径  
2. 编排Hook系统的自动触发
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ...services.url_mapping import get_url_mapping_service
from ..metadata.registry import get_global_registry
from ..metadata.base import IdentifierData
from .routing import RouteManager
from .data_pipeline import DataPipeline

logger = logging.getLogger(__name__)


class SmartRouter:
    """智能路由器 - 专注路由选择和Hook编排"""
    
    def __init__(self, dao=None):
        # 路由组件
        self.url_mapping_service = get_url_mapping_service()
        self.metadata_registry = get_global_registry()
        self.route_manager = RouteManager()
        
        # 数据管道 (负责所有数据库操作)
        self.data_pipeline = DataPipeline(dao) if dao else None
        
    async def route_and_process(self, url: str, source_data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        智能路由和处理入口
        
        Args:
            url: 输入URL
            source_data: 源数据
            task_id: 任务ID
            
        Returns:
            处理结果
        """
        logger.info(f"🚀 [智能路由] 开始处理: {url}")
        start_time = datetime.now()
        
        try:
            # 阶段1: URL映射 - 提取基础标识符
            mapping_result = await self._perform_url_mapping(url)
            
            # 阶段2: 路由决策 - 选择最优处理路径
            route = self.route_manager.determine_route(url, mapping_result)
            logger.info(f"🎯 [智能路由] 选择路由: {route.name} (处理器: {route.processors})")
            
            # 阶段3: 执行选定的处理器获取原始数据
            raw_data = await self._execute_processors(route, source_data, mapping_result)
            
            # 🔧 检查raw_data是否有效
            if not raw_data:
                logger.error(f"[智能路由] 处理器执行返回空数据")
                return {
                    'status': 'failed',
                    'error': 'Processor execution returned no data',
                    'execution_time': (datetime.now() - start_time).total_seconds(),
                    'fallback_to_legacy': True
                }
            
            # 阶段4: 数据管道处理 - 统一的去重、写入、Hook触发
            if self.data_pipeline:
                pipeline_result = await self.data_pipeline.process_data(
                    raw_data=raw_data,
                    source_data=source_data,
                    mapping_result=mapping_result,
                    route_info={'name': route.name, 'processors': route.processors},
                    task_id=task_id
                )
                
                execution_time = (datetime.now() - start_time).total_seconds()
                pipeline_result['execution_time'] = execution_time
                pipeline_result['route_used'] = route.name
                
                logger.info(f"✅ [智能路由] 处理完成: {execution_time:.2f}s")
                return pipeline_result
            else:
                # 没有数据管道时的简化返回
                execution_time = (datetime.now() - start_time).total_seconds()
                return {
                    'status': 'completed',
                    'route_used': route.name,
                    'execution_time': execution_time,
                    'raw_data': raw_data,
                    'note': 'No data pipeline configured'
                }
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [智能路由] 处理失败: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'execution_time': execution_time,
                'fallback_to_legacy': True
            }
    
    async def _perform_url_mapping(self, url: str) -> Optional[Dict]:
        """执行URL映射 - 复用现有服务"""
        try:
            logger.debug(f"🔍 [智能路由] URL映射: {url}")
            # 🔧 修复：URL映射服务的map_url是异步方法，需要await
            mapping_result = await self.url_mapping_service.map_url(url)
            
            if mapping_result and mapping_result.is_successful():
                result_dict = mapping_result.to_dict()
                logger.info(f"✅ [智能路由] URL映射成功: {len([k for k, v in result_dict.items() if v])} 个字段")
                return result_dict
            else:
                logger.warning(f"⚠️ [智能路由] URL映射无结果: {url}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ [智能路由] URL映射失败: {url}, 错误: {e}")
            return None
    
    async def _execute_processors(self, route, source_data: Dict, mapping_result: Optional[Dict]) -> Dict[str, Any]:
        """执行处理器获取原始数据 - 不涉及数据库操作"""
        
        # 准备标识符数据
        identifier_data = self._prepare_identifier_data(source_data, mapping_result)
        
        # 获取可用的处理器
        available_processors = self._get_available_processors(route.processors, identifier_data)
        
        if not available_processors:
            logger.warning(f"[智能路由] 未找到可用处理器，路由: {route.name}")
            return {'processors_attempted': route.processors, 'available_processors': 0}
        
        logger.info(f"🎪 [智能路由] 可用处理器: {[p.name for p in available_processors]}")
        
        # 根据路由类型执行处理器
        if self.route_manager.is_fast_path(route):
            return await self._execute_fast_path(available_processors, identifier_data)
        else:
            return await self._execute_standard_path(available_processors, identifier_data)
    
    async def _execute_fast_path(self, processors, identifier_data: IdentifierData) -> Dict[str, Any]:
        """快速路径 - 只用第一个处理器"""
        processor = processors[0]
        logger.info(f"⚡ [智能路由] 快速路径: {processor.name}")
        
        try:
            # 兼容同步/异步处理器
            if hasattr(processor.process, '__call__'):
                import inspect
                if inspect.iscoroutinefunction(processor.process):
                    result = await processor.process(identifier_data)
                else:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, processor.process, identifier_data)
            else:
                raise AttributeError(f"Processor {processor.name} has no process method")
            
            if result and result.is_valid:
                logger.info(f"✅ [智能路由] 快速路径成功: {processor.name}")
                return {
                    'processor_used': processor.name,
                    'confidence': result.confidence,
                    'metadata': result.metadata,
                    'new_identifiers': result.new_identifiers,
                    'success': True
                }
            else:
                logger.warning(f"⚠️ [智能路由] 快速路径失败: {processor.name}")
                return {
                    'processor_used': processor.name,
                    'error': result.error if result else 'No result',
                    'success': False
                }
                
        except Exception as e:
            logger.error(f"❌ [智能路由] 快速路径异常: {processor.name}, {e}")
            return {
                'processor_used': processor.name,
                'error': str(e),
                'success': False
            }
    
    async def _execute_standard_path(self, processors, identifier_data: IdentifierData) -> Dict[str, Any]:
        """标准路径 - 并行执行多个处理器"""
        logger.info(f"🔄 [智能路由] 标准路径: {[p.name for p in processors]}")
        
        # 简化版本：依次尝试处理器，找到第一个成功的
        for processor in processors:
            try:
                # 兼容同步/异步处理器
                import inspect
                if inspect.iscoroutinefunction(processor.process):
                    result = await processor.process(identifier_data)
                else:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, processor.process, identifier_data)
                
                if result and result.is_valid:
                    logger.info(f"✅ [智能路由] 标准路径成功: {processor.name}")
                    return {
                        'processor_used': processor.name,
                        'confidence': result.confidence,
                        'metadata': result.metadata,
                        'new_identifiers': result.new_identifiers,
                        'success': True
                    }
                else:
                    logger.debug(f"[智能路由] 处理器失败，尝试下一个: {processor.name}")
                    
            except Exception as e:
                logger.debug(f"[智能路由] 处理器异常，尝试下一个: {processor.name}, {e}")
                continue
        
        # 所有处理器都失败
        return {
            'processors_attempted': [p.name for p in processors],
            'error': 'All processors failed',
            'success': False
        }
    
    def _prepare_identifier_data(self, source_data: Dict, mapping_result: Optional[Dict]) -> IdentifierData:
        """准备标识符数据"""
        
        # 基础标识符
        identifier_data = IdentifierData(
            doi=source_data.get("doi"),
            arxiv_id=source_data.get("arxiv_id"),
            pmid=source_data.get("pmid"),
            url=source_data.get("url"),
            source_data=source_data
        )
        
        # 从URL映射结果中提取增强信息
        if mapping_result:
            identifier_data.title = mapping_result.get("title")
            identifier_data.year = mapping_result.get("year")
            identifier_data.venue = mapping_result.get("venue")
            identifier_data.authors = mapping_result.get("authors")
            
            # 更新标识符
            if mapping_result.get("doi"):
                identifier_data.doi = mapping_result["doi"]
            if mapping_result.get("arxiv_id"):
                identifier_data.arxiv_id = mapping_result["arxiv_id"]
                
        return identifier_data
    
    def _get_available_processors(self, processor_names: List[str], identifier_data: IdentifierData):
        """获取可用的处理器实例"""
        available = []
        
        for name in processor_names:
            try:
                processor = self.metadata_registry.get_processor(name)
                if processor.can_handle(identifier_data):
                    available.append(processor)
                else:
                    logger.debug(f"[智能路由] 处理器无法处理: {name}")
            except KeyError:
                logger.warning(f"[智能路由] 处理器未注册: {name}")
            except Exception as e:
                logger.warning(f"[智能路由] 获取处理器失败: {name}, 错误: {e}")
                
        return available
