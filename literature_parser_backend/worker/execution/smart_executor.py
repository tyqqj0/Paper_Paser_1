"""
智能执行器

基于路由的智能处理器执行系统，自动判断并行执行。
"""

import asyncio
import inspect
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime

from ...services.url_mapping import get_url_mapping_service
from ..metadata.registry import get_global_registry
from ..metadata.base import IdentifierData
from .routing import RouteManager
from .hooks import HookManager

logger = logging.getLogger(__name__)


class ExecutionContext:
    """执行上下文 - 跟踪执行状态和数据"""
    
    def __init__(self, task_id: str, source_data: Dict[str, Any]):
        self.task_id = task_id
        self.source_data = source_data
        self.url = source_data.get('url', '')
        
        # 执行状态
        self.executed_processors: Set[str] = set()
        self.results: Dict[str, Any] = {}
        self.metadata = None
        self.identifiers = {}
        
        # 时间跟踪
        self.start_time = datetime.now()
        self.processor_times: Dict[str, float] = {}
        
    def mark_processor_executed(self, processor_name: str, execution_time: float):
        """标记处理器已执行"""
        self.executed_processors.add(processor_name)
        self.processor_times[processor_name] = execution_time
        logger.debug(f"处理器 {processor_name} 执行完成，耗时: {execution_time:.2f}s")
        
    def update_metadata(self, metadata, source: str):
        """更新元数据"""
        if metadata:
            self.metadata = metadata
            self.results[f'metadata_from_{source}'] = metadata
            logger.info(f"✅ 元数据已更新，来源: {source}")
            
    def update_identifiers(self, identifiers: Dict[str, Any]):
        """更新标识符"""
        if identifiers:
            self.identifiers.update(identifiers)
            logger.debug(f"标识符已更新: {identifiers}")


class SmartExecutor:
    """智能执行器 - 核心执行逻辑"""
    
    def __init__(self, dao=None):
        # 复用现有组件
        self.url_mapping_service = get_url_mapping_service()
        self.metadata_registry = get_global_registry()
        self.route_manager = RouteManager.get_instance()
        
        # 🆕 Hook系统 (如果提供了DAO)
        self.hook_manager = HookManager(dao) if dao else None
        
    async def execute_by_route(self, url: str, source_data: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """
        基于路由的智能执行入口
        
        Args:
            url: 输入URL
            source_data: 源数据
            task_id: 任务ID
            
        Returns:
            执行结果
        """
        logger.info(f"🚀 智能执行器启动: {url}")
        start_time = datetime.now()
        
        # 创建执行上下文
        context = ExecutionContext(task_id, source_data)
        
        try:
            # 阶段1: URL映射 (复用现有服务)
            mapping_result = await self._perform_url_mapping(url)
            
            # 阶段2: 路由决策
            route = self.route_manager.determine_route(url, mapping_result)
            
            # 阶段3: 智能执行处理器
            execution_results = await self._execute_processors_smart(route, context, mapping_result)
            
            # 阶段4: 结果整合
            final_result = self._build_final_result(context, execution_results, route)
            
            # 🆕 阶段5: Hook后处理
            if self.hook_manager and final_result.get('status') == 'completed':
                await self._trigger_post_processing_hooks(final_result, context)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            final_result['execution_time'] = execution_time
            
            logger.info(f"✅ 智能执行完成: {url}, 耗时: {execution_time:.2f}s, 路由: {route.name}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"❌ 智能执行失败: {url}, 错误: {e}")
            # 返回错误信息，让上层决定是否回退到原有逻辑
            return {
                'status': 'failed',
                'error': str(e),
                'fallback_to_legacy': True,
                'execution_time': (datetime.now() - start_time).total_seconds()
            }
    
    async def _perform_url_mapping(self, url: str) -> Optional[Dict]:
        """执行URL映射 (复用现有服务)"""
        try:
            logger.debug(f"🎯 执行URL映射: {url}")
            mapping_result = self.url_mapping_service.map_url(url)  # ✅ 移除await，这是同步方法
            
            if mapping_result and mapping_result.is_successful():
                result_dict = mapping_result.to_dict()
                logger.info(f"✅ URL映射成功: 找到 {len([k for k, v in result_dict.items() if v])} 个有效字段")
                return result_dict
            else:
                logger.warning(f"⚠️ URL映射未找到标识符: {url}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ URL映射失败: {url}, 错误: {e}")
            return None
    
    async def _execute_processors_smart(self, route, context: ExecutionContext, mapping_result: Optional[Dict]) -> List[Dict]:
        """智能执行处理器 - 自动判断并行"""
        
        # 准备标识符数据
        identifier_data = self._prepare_identifier_data(context.source_data, mapping_result)
        
        # 获取可用的处理器
        available_processors = self._get_available_processors(route.processors, identifier_data)
        
        if not available_processors:
            logger.warning(f"未找到可用的处理器，路由: {route.name}")
            return []
        
        logger.info(f"🎪 可用处理器: {[p.name for p in available_processors]} (路由: {route.name})")
        
        # 根据路由类型决定执行策略
        if self.route_manager.is_fast_path(route):
            return await self._execute_fast_path(available_processors, identifier_data, context)
        else:
            return await self._execute_parallel_processors(available_processors, identifier_data, context)
    
    async def _execute_fast_path(self, processors, identifier_data: IdentifierData, context: ExecutionContext) -> List[Dict]:
        """快速路径执行 - 只使用第一个处理器"""
        if not processors:
            return []
            
        processor = processors[0]  # 快速路径只用最优处理器
        logger.info(f"⚡ 快速路径执行: {processor.name}")
        
        start_time = datetime.now()
        try:
            # 🔧 检查处理器的process方法是否是异步的
            if inspect.iscoroutinefunction(processor.process):
                # 异步处理器
                result = await processor.process(identifier_data)
            else:
                # 同步处理器，在线程池中执行
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, processor.process, identifier_data)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            context.mark_processor_executed(processor.name, execution_time)
            
            if result.is_valid:
                context.update_metadata(result.metadata, processor.name)
                if result.new_identifiers:
                    context.update_identifiers(result.new_identifiers)
                return [{'processor': processor.name, 'result': result, 'success': True}]
            else:
                logger.warning(f"⚠️ 快速路径处理器失败: {processor.name}, 错误: {result.error}")
                return [{'processor': processor.name, 'result': result, 'success': False}]
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            context.mark_processor_executed(processor.name, execution_time)
            logger.error(f"❌ 快速路径处理器异常: {processor.name}, 错误: {e}")
            return [{'processor': processor.name, 'error': str(e), 'success': False}]
    
    async def _execute_parallel_processors(self, processors, identifier_data: IdentifierData, context: ExecutionContext) -> List[Dict]:
        """并行执行多个处理器"""
        logger.info(f"🔄 并行执行处理器: {[p.name for p in processors]}")
        
        # 创建并行任务
        tasks = {}
        for processor in processors:
            task = asyncio.create_task(self._execute_single_processor(processor, identifier_data, context))
            tasks[processor.name] = task
        
        # 等待所有任务完成 (或快速失败)
        results = []
        completed_tasks = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        for i, (processor_name, result) in enumerate(zip(tasks.keys(), completed_tasks)):
            if isinstance(result, Exception):
                logger.error(f"❌ 处理器异常: {processor_name}, 错误: {result}")
                results.append({'processor': processor_name, 'error': str(result), 'success': False})
            else:
                results.append(result)
        
        # 统计成功的处理器
        successful = [r for r in results if r.get('success')]
        logger.info(f"📊 处理器执行完成: {len(successful)}/{len(processors)} 成功")
        
        return results
    
    async def _execute_single_processor(self, processor, identifier_data: IdentifierData, context: ExecutionContext) -> Dict:
        """执行单个处理器 - 自动处理async/sync兼容性"""
        start_time = datetime.now()
        
        try:
            # 🔧 检查处理器的process方法是否是异步的
            if inspect.iscoroutinefunction(processor.process):
                # 异步处理器
                result = await processor.process(identifier_data)
            else:
                # 同步处理器，在线程池中执行
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, processor.process, identifier_data)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            context.mark_processor_executed(processor.name, execution_time)
            
            if result.is_valid:
                context.update_metadata(result.metadata, processor.name)
                if result.new_identifiers:
                    context.update_identifiers(result.new_identifiers)
                    
                logger.info(f"✅ 处理器成功: {processor.name} (置信度: {result.confidence:.2f})")
                return {'processor': processor.name, 'result': result, 'success': True}
            else:
                logger.warning(f"⚠️ 处理器失败: {processor.name}, 错误: {result.error}")
                return {'processor': processor.name, 'result': result, 'success': False}
                
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            context.mark_processor_executed(processor.name, execution_time)
            logger.error(f"❌ 处理器异常: {processor.name}, 错误: {e}")
            return {'processor': processor.name, 'error': str(e), 'success': False}
    
    def _prepare_identifier_data(self, source_data: Dict, mapping_result: Optional[Dict]) -> IdentifierData:
        """准备标识符数据 (复用现有逻辑)"""
        
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
                    logger.debug(f"处理器 {name} 无法处理当前标识符")
            except KeyError:
                logger.warning(f"未找到处理器: {name}")
            except Exception as e:
                logger.warning(f"获取处理器失败: {name}, 错误: {e}")
                
        return available
    
    def _build_final_result(self, context: ExecutionContext, execution_results: List[Dict], route) -> Dict[str, Any]:
        """构建最终结果"""
        
        # 选择最佳结果
        successful_results = [r for r in execution_results if r.get('success')]
        
        if successful_results:
            # 选择置信度最高的结果
            best_result = max(successful_results, 
                            key=lambda r: r.get('result', {}).get('confidence', 0))
            
            total_time = (datetime.now() - context.start_time).total_seconds()
            
            return {
                'status': 'completed',
                'result_type': 'created',  # 暂时硬编码，后续通过Hook处理
                'literature_id': f"smart-route-{context.task_id[:8]}",  # 临时ID，用于演示
                'metadata': context.metadata,
                'processor_used': best_result['processor'],
                'confidence': best_result['result'].confidence,
                'route_used': route.name,
                'execution_time': total_time,
                'processor_times': context.processor_times,
                'url_validation_status': 'success',
                'original_url': context.url
            }
        else:
            # 所有处理器都失败
            return {
                'status': 'failed',
                'error': 'All processors failed',
                'attempted_processors': [r.get('processor') for r in execution_results],
                'route_used': route.name,
                'execution_time': (datetime.now() - context.start_time).total_seconds(),
                'fallback_to_legacy': True  # 建议回退到原有逻辑
            }
    
    async def _trigger_post_processing_hooks(self, final_result: Dict, context: ExecutionContext):
        """触发后处理Hook"""
        try:
            if not self.hook_manager:
                return
            
            # 准备Hook上下文
            hook_context = {
                'literature_id': final_result.get('literature_id'),
                'metadata': context.metadata,
                'url_info': {'url': context.url},
                'processor_used': final_result.get('processor_used'),
                'confidence': final_result.get('confidence'),
                'task_id': context.task_id
            }
            
            # 触发文献创建事件
            if final_result.get('result_type') == 'created':
                logger.info(f"🎯 [Hook] 触发文献创建事件: {hook_context['literature_id']}")
                hook_results = await self.hook_manager.trigger_event('literature_created', hook_context)
                final_result['hook_results'] = hook_results
            
            # 触发元数据更新事件
            if context.metadata:
                logger.info(f"🎯 [Hook] 触发元数据更新事件: {hook_context['literature_id']}")
                hook_results = await self.hook_manager.trigger_event('metadata_updated', hook_context)
                final_result['hook_results'] = hook_results
                
        except Exception as e:
            logger.error(f"❌ Hook后处理失败: {e}")
            # Hook失败不应该影响主流程
