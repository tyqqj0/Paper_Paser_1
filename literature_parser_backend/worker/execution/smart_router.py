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
from .hooks import HookManager

logger = logging.getLogger(__name__)


class SmartRouter:
    """智能路由器 - 专注路由选择和Hook编排"""
    
    def __init__(self, dao=None):
        # 路由组件
        self.url_mapping_service = get_url_mapping_service()
        self.metadata_registry = get_global_registry()
        self.route_manager = RouteManager.get_instance()
        
        # 🆕 Hook管理器
        self.hook_manager = HookManager(dao) if dao else None
        
        # 数据管道 (负责所有数据库操作)
        self.data_pipeline = DataPipeline(dao, self.hook_manager) if dao else None
        
    def can_handle(self, url: str) -> bool:
        """
        判断SmartRouter是否能处理此URL
        
        Args:
            url: 输入URL
            
        Returns:
            True if 可以通过智能路由处理，False if 需要回退到legacy处理
        """
        if not url:
            return False
            
        try:
            # 使用RouteManager判断是否有合适的路由
            route = self.route_manager.determine_route(url)
            
            # 如果找到了非兜底路由，说明可以处理
            if route and route.name != "fallback_route":
                logger.debug(f"🎯 SmartRouter可以处理: {url} -> {route.name}")
                return True
            else:
                logger.debug(f"⚠️ SmartRouter无法处理: {url} -> 回退到legacy")
                return False
                
        except Exception as e:
            logger.warning(f"❌ SmartRouter路由判断异常: {url} -> {e}")
            return False

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
        # available_processors = self._get_available_processors(route.processors, identifier_data)
        available_processors = []
        for processor_name in route.processors:
            processor = self.metadata_registry.get_processor(processor_name)
            if processor:
                available_processors.append(processor)
            else:
                logger.warning(f"[智能路由] 未找到处理器: {processor_name}")
        
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
        """快速路径 - 使用统一的处理逻辑"""
        logger.info(f"⚡ [智能路由] 快速路径: {[p.name for p in processors]}")
        return await self._execute_processors_unified(processors, identifier_data, is_fast_path=True)
    
    async def _execute_standard_path(self, processors, identifier_data: IdentifierData) -> Dict[str, Any]:
        """标准路径 - 使用统一的处理逻辑"""
        logger.info(f"🔄 [智能路由] 标准路径: {[p.name for p in processors]}")
        return await self._execute_processors_unified(processors, identifier_data, is_fast_path=False)
    
    async def _execute_processors_unified(self, processors, identifier_data: IdentifierData, is_fast_path: bool = False) -> Dict[str, Any]:
        """
        统一的处理器执行逻辑，支持metadata和identifiers累积合并
        
        核心逻辑：
        1. 按顺序选择列表中最靠前的可用且未用过的处理器
        2. 执行处理器获得结果
        3. 累积合并metadata和new_identifiers
        4. 如果结果有效且完整(is_complete_parsing)，则停止
        5. 否则继续下一个处理器
        6. 返回最佳结果配合累积的metadata和identifiers
        """
        path_type = "快速路径" if is_fast_path else "标准路径"
        attempted_processors = []
        used_processors = set()  # 跟踪已使用的处理器
        
        # 累积数据存储
        accumulated_metadata = {}
        accumulated_identifiers = []
        best_result = None
        best_confidence = 0.0
        
        while True:
            # 选择下一个可用且未用过的处理器
            next_processor = self._get_next_available_processor(processors, used_processors, identifier_data)
            
            if not next_processor:
                # 没有更多可用处理器
                logger.info(f"🏁 [{path_type}] 所有可用处理器已尝试完毕")
                break
            
            # 标记为已使用
            used_processors.add(next_processor.name)
            attempted_processors.append(next_processor.name)
            
            logger.info(f"🔍 [{path_type}] 尝试处理器: {next_processor.name}")
            
            try:
                # 执行处理器
                result = await self._execute_single_processor(next_processor, identifier_data)
                
                if result:
                    # 计算解析分数
                    parsing_score = result.get_parsing_score()
                    
                    # 🆕 详细调试信息
                    logger.info(f"🔍 [{path_type}] 处理器结果详情: {next_processor.name}")
                    logger.info(f"  📊 分数: {parsing_score:.3f}, 置信度: {result.confidence:.3f}")
                    
                    # 修复：MetadataModel对象没有len()方法，改为检查是否存在
                    metadata_status = "有效" if result.metadata and result.metadata.title else "无效"
                    logger.info(f"  📝 Metadata状态: {metadata_status}")
                    logger.info(f"  🆔 新Identifiers数: {len(result.new_identifiers) if result.new_identifiers else 0}")
                    
                    if result.metadata:
                        # 修复：MetadataModel对象不能用get()方法，直接访问属性
                        title = result.metadata.title or 'N/A'
                        logger.info(f"  📖 标题: {title[:50]}{'...' if len(title) > 50 else ''}")
                        
                        authors = result.metadata.authors or []
                        author_names = []
                        for a in authors[:3]:
                            if isinstance(a, dict):
                                author_names.append(a.get('name', 'N/A'))
                            else:
                                author_names.append(str(a))
                        logger.info(f"  👥 作者数: {len(authors)} - {author_names}")
                        logger.info(f"  📅 年份: {result.metadata.year or 'N/A'}")
                        logger.info(f"  📚 期刊: {result.metadata.journal or 'N/A'}")
                    
                    if parsing_score > 0.0:
                        # 非零分：有价值的结果
                        logger.info(f"✅ [{path_type}] 处理器产生有效结果: {next_processor.name}")
                        
                        # 累积合并metadata和identifiers（所有非零分结果都要合并）
                        self._merge_metadata(accumulated_metadata, result.metadata, next_processor.name)
                        self._merge_identifiers(accumulated_identifiers, result.new_identifiers, next_processor.name)
                        
                        # 🆕 更新identifier_data，为后续处理器提供更多信息
                        identifier_data = self._update_identifier_data_from_result(identifier_data, result)
                        
                        # 更新最佳主要结果的条件
                        is_better_result = (
                            best_result is None or 
                            parsing_score > best_result.get_parsing_score() or
                            (parsing_score == best_result.get_parsing_score() and result.confidence > best_confidence)
                        )
                        
                        # 🔍 调试：检查best_result更新逻辑
                        logger.debug(f"🔍 [{path_type}] best_result更新检查:")
                        logger.debug(f"  当前best_result: {best_result is not None}")
                        logger.debug(f"  当前分数: {parsing_score:.3f}")
                        logger.debug(f"  is_better_result: {is_better_result}")
                        
                        if is_better_result:
                            best_result = result
                            best_confidence = result.confidence
                            logger.info(f"📈 [{path_type}] 更新最佳主结果: {next_processor.name} (分数: {parsing_score:.3f})")
                        else:
                            logger.debug(f"🔄 [{path_type}] 未更新best_result: {next_processor.name}")
                        
                        # 满分检查 - 如果满分就立即停止
                        if parsing_score >= 1.0:
                            logger.info(f"🚀 [{path_type}] 满分解析，立即停止: {next_processor.name} (分数: {parsing_score:.3f})")
                            break
                        elif is_fast_path and best_result:
                            # 快速路径：得到有效结果就返回（即使不满分）
                            logger.info(f"⚡ [{path_type}] 快速路径获得有效结果，直接返回 (分数: {parsing_score:.3f})")
                            break
                        else:
                            # 标准路径：非满分但有效，继续寻找更好的结果
                            logger.info(f"🔄 [{path_type}] 非满分但有效，继续寻找更好结果 (当前分数: {parsing_score:.3f})")
                    else:
                        # 零分：无效结果，继续尝试
                        logger.debug(f"❌ [{path_type}] 处理器零分，继续尝试: {next_processor.name}")
                        
                else:
                    logger.debug(f"❌ [{path_type}] 处理器返回空结果: {next_processor.name}")
                    
            except Exception as e:
                logger.debug(f"💥 [{path_type}] 处理器异常，继续尝试: {next_processor.name}, {e}")
                continue
        
        # 构建最终结果
        if best_result:
            final_parsing_score = best_result.get_parsing_score()
            
            final_result = {
                'processor_used': best_result.processor_name if hasattr(best_result, 'processor_name') else 'unknown',
                'confidence': best_result.confidence,
                'parsing_score': final_parsing_score,  # 添加解析分数
                'metadata': best_result.metadata,  # 🔧 使用主处理器的原始MetadataModel对象，而不是累积字典
                'accumulated_metadata': accumulated_metadata,  # 保留累积数据用于调试
                'new_identifiers': accumulated_identifiers,  # 使用累积的identifiers
                'success': True,
                'attempted_processors': attempted_processors,
                'metadata_sources': list(set([meta.get('source_processor', 'unknown') for meta in accumulated_metadata.values() if isinstance(meta, dict)])),
                'is_complete': final_parsing_score >= 1.0,  # 是否为满分
                'accumulation_summary': {
                    'total_metadata_fields': len(accumulated_metadata),
                    'total_identifiers': len(accumulated_identifiers),
                    'contributing_processors': len(set(attempted_processors))
                }
            }
            
            logger.info(f"🏆 [{path_type}] 最终结果: 主处理器={final_result['processor_used']}, "
                       f"解析分数={final_parsing_score:.3f}, "
                       f"metadata来源={len(final_result['metadata_sources'])}个处理器, "
                       f"累积identifiers={len(accumulated_identifiers)}个")
            
            return final_result
        else:
            # 所有处理器都产生零分结果
            logger.warning(f"❌ [{path_type}] 所有处理器都产生零分结果")
            return {
                'processors_attempted': attempted_processors,
                'error': 'All processors produced zero-score results',
                'success': False,
                'parsing_score': 0.0
            }
    
    def _merge_metadata(self, accumulated_metadata: Dict, new_metadata: Dict, processor_name: str):
        """
        合并metadata，避免覆盖已有数据
        
        策略：
        1. 对于相同的key，如果值不同，保留更详细的或创建列表
        2. 为每个数据添加来源标记
        3. 优先保留更完整的数据
        """
        if not new_metadata:
            return
        
        # 🔧 修复：处理MetadataModel对象
        if hasattr(new_metadata, '__dict__') and not isinstance(new_metadata, dict):
            # MetadataModel对象，转换为字典
            metadata_dict = {}
            for attr_name in dir(new_metadata):
                if not attr_name.startswith('_') and not callable(getattr(new_metadata, attr_name)):
                    value = getattr(new_metadata, attr_name)
                    if value is not None:
                        metadata_dict[attr_name] = value
            new_metadata = metadata_dict
        
        # 现在new_metadata肯定是字典了
        logger.debug(f"🔄 [合并] {processor_name} 贡献 {len(new_metadata)} 个字段到已有的{len(accumulated_metadata)}个字段中")
        
        for key, value in new_metadata.items():
            if key not in accumulated_metadata:
                # 新字段，直接添加
                accumulated_metadata[key] = {
                    'value': value,
                    'source_processor': processor_name,
                    'confidence': getattr(value, 'confidence', 1.0) if hasattr(value, 'confidence') else 1.0
                }
                logger.debug(f"🆕 [合并] 新增字段 '{key}': {self._format_value_for_debug(value)} (来源: {processor_name})")
            else:
                # 已存在的字段，需要智能合并
                existing = accumulated_metadata[key]
                existing_value = existing.get('value') if isinstance(existing, dict) else existing
                
                # 比较值的完整性和质量
                if self._is_better_metadata_value(value, existing_value):
                    logger.debug(f"📈 [合并] 更新字段 '{key}': {self._format_value_for_debug(value)} "
                                f"({processor_name}) 替换 {self._format_value_for_debug(existing_value)} "
                                f"({existing.get('source_processor', 'unknown')})")
                    accumulated_metadata[key] = {
                        'value': value,
                        'source_processor': processor_name,
                        'confidence': getattr(value, 'confidence', 1.0) if hasattr(value, 'confidence') else 1.0,
                        'previous_value': existing_value,
                        'previous_source': existing.get('source_processor', 'unknown')
                    }
                elif value != existing_value:
                    # 值不同但新值不一定更好，记录为alternative
                    if 'alternatives' not in accumulated_metadata[key]:
                        accumulated_metadata[key]['alternatives'] = []
                    accumulated_metadata[key]['alternatives'].append({
                        'value': value,
                        'source_processor': processor_name
                    })
                    logger.debug(f"🔄 [合并] 保留原值 '{key}': {self._format_value_for_debug(existing_value)} "
                                f"({existing.get('source_processor', 'unknown')})，"
                                f"新值作为备选: {self._format_value_for_debug(value)} ({processor_name})")
                else:
                    logger.debug(f"🔄 [合并] 字段 '{key}' 值相同，跳过")
    
    def _merge_identifiers(self, accumulated_identifiers: List, new_identifiers: List, processor_name: str):
        """
        合并new_identifiers，避免重复
        
        策略：
        1. 按identifier的值去重
        2. 保留来源信息
        3. 合并相同identifier的不同属性
        """
        if not new_identifiers:
            return
            
        logger.debug(f"🔄 [合并] {processor_name} 贡献 {len(new_identifiers)} 个标识符到已有的{len(accumulated_identifiers)}个中")
        
        # 创建现有identifiers的索引（按值）
        existing_index = {}
        for i, existing_id in enumerate(accumulated_identifiers):
            key = self._get_identifier_key(existing_id)
            existing_index[key] = i
        
        # 处理新的identifiers
        for new_id in new_identifiers:
            key = self._get_identifier_key(new_id)
            
            if key in existing_index:
                # 已存在，合并属性
                existing_idx = existing_index[key]
                existing_id = accumulated_identifiers[existing_idx]
                
                # 合并属性（如confidence, source等）
                merged_id = self._merge_identifier_attributes(existing_id, new_id, processor_name)
                accumulated_identifiers[existing_idx] = merged_id
                logger.debug(f"🔗 [合并] 合并重复标识符: {key} (来源: {processor_name})")
            else:
                # 新identifier，添加来源信息
                enhanced_id = dict(new_id) if isinstance(new_id, dict) else {'value': new_id}
                enhanced_id['discovered_by'] = processor_name
                accumulated_identifiers.append(enhanced_id)
                existing_index[key] = len(accumulated_identifiers) - 1
                logger.debug(f"➕ [合并] 新增标识符: {key} (来源: {processor_name})")
    
    def _is_better_metadata_value(self, new_value, existing_value):
        """判断新的metadata值是否比现有值更好"""
        # 如果现有值为空或None，新值总是更好
        if not existing_value:
            return bool(new_value)
        
        # 如果新值为空，保持现有值
        if not new_value:
            return False
        
        # 字符串长度比较（更长通常意味着更详细）
        if isinstance(new_value, str) and isinstance(existing_value, str):
            return len(new_value) > len(existing_value)
        
        # 列表长度比较
        if isinstance(new_value, list) and isinstance(existing_value, list):
            return len(new_value) > len(existing_value)
        
        # 字典字段数量比较
        if isinstance(new_value, dict) and isinstance(existing_value, dict):
            return len(new_value) > len(existing_value)
        
        # 如果有confidence属性，比较confidence
        new_conf = getattr(new_value, 'confidence', 0)
        existing_conf = getattr(existing_value, 'confidence', 0)
        if new_conf != existing_conf:
            return new_conf > existing_conf
        
        # 默认保持现有值
        return False
    
    def _get_identifier_key(self, identifier):
        """获取identifier的唯一键用于去重"""
        if isinstance(identifier, dict):
            # 使用type和value组合作为key
            return f"{identifier.get('type', 'unknown')}:{identifier.get('value', '')}"
        else:
            # 简单值直接使用
            return str(identifier)
    
    def _merge_identifier_attributes(self, existing_id, new_id, processor_name):
        """合并两个相同identifier的属性"""
        if isinstance(existing_id, dict) and isinstance(new_id, dict):
            merged = existing_id.copy()
            
            # 合并属性
            for key, value in new_id.items():
                if key not in merged:
                    merged[key] = value
                elif key == 'confidence':
                    # 取更高的confidence
                    merged[key] = max(merged.get(key, 0), value)
                elif key == 'discovered_by':
                    # 记录多个发现者
                    existing_sources = merged.get('discovered_by', [])
                    if isinstance(existing_sources, str):
                        existing_sources = [existing_sources]
                    if processor_name not in existing_sources:
                        existing_sources.append(processor_name)
                    merged['discovered_by'] = existing_sources
            
            # 添加当前处理器为发现者
            if 'discovered_by' not in merged:
                merged['discovered_by'] = [existing_id.get('discovered_by', 'unknown'), processor_name]
            
            return merged
        else:
            # 简单值，返回现有的
            return existing_id
    
    def _get_next_available_processor(self, processors, used_processors, identifier_data):
        """获取下一个可用且未用过的处理器（按列表顺序）"""
        logger.debug(f"🔍 寻找可用处理器: 总数={len(processors)}, 已用={list(used_processors)}")
        
        for processor in processors:
            if processor.name in used_processors:
                logger.debug(f"⏭️ 跳过已使用处理器: {processor.name}")
                continue
                
            can_handle = processor.can_handle(identifier_data)
            logger.debug(f"🤔 检查处理器 {processor.name}: can_handle={can_handle}")
            
            # 🆕 详细调试：显示当前identifier_data状态
            logger.debug(f"  🔍 当前identifier_data状态:")
            logger.debug(f"    📖 title: {identifier_data.title[:50] if identifier_data.title else 'None'}{'...' if identifier_data.title and len(identifier_data.title) > 50 else ''}")
            logger.debug(f"    👥 authors: {len(identifier_data.authors) if identifier_data.authors else 0} 个")
            logger.debug(f"    🔗 doi: {identifier_data.doi or 'None'}")
            logger.debug(f"    📄 arxiv_id: {identifier_data.arxiv_id or 'None'}")
            logger.debug(f"    🌐 url: {identifier_data.url or 'None'}")
            
            if can_handle:
                logger.info(f"✅ 选择处理器: {processor.name}")
                return processor
            else:
                logger.debug(f"❌ 处理器无法处理当前标识符: {processor.name}")
        
        logger.warning(f"❌ 没有找到可用的处理器 (剩余未用: {[p.name for p in processors if p.name not in used_processors]})")
        return None
    
    async def _execute_single_processor(self, processor, identifier_data: IdentifierData):
        """执行单个处理器（兼容同步/异步）"""
        if hasattr(processor.process, '__call__'):
            import inspect
            if inspect.iscoroutinefunction(processor.process):
                result = await processor.process(identifier_data)
            else:
                import asyncio
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, processor.process, identifier_data)
            
            # 确保结果包含处理器名称
            if result:
                result.processor_name = processor.name
                result.source = processor.name  # 也设置source字段
            
            return result
        else:
            raise AttributeError(f"Processor {processor.name} has no process method")
    
    def _update_identifier_data_from_result(self, identifier_data: IdentifierData, result) -> IdentifierData:
        """基于处理器结果更新identifier_data，为后续处理器提供更多信息"""
        if not result or not result.metadata:
            logger.debug(f"🔄 [更新] 无结果或metadata，保持原identifier_data")
            return identifier_data
            
        logger.debug(f"🔄 [更新] 开始从处理器结果更新identifier_data")
            
        # 创建新的identifier_data副本
        updated_data = IdentifierData(
            doi=identifier_data.doi,
            arxiv_id=identifier_data.arxiv_id,
            pmid=identifier_data.pmid,
            semantic_scholar_id=identifier_data.semantic_scholar_id,
            url=identifier_data.url,
            pdf_url=identifier_data.pdf_url,
            title=identifier_data.title,
            year=identifier_data.year,
            venue=identifier_data.venue,
            authors=identifier_data.authors,
            source_data=identifier_data.source_data,
            pdf_content=identifier_data.pdf_content,
            file_path=identifier_data.file_path
        )
        
        # 从结果中更新字段（如果identifier_data中还没有这些信息）
        metadata = result.metadata
        
        # 🔧 修复：MetadataModel对象没有get()方法，直接访问属性
        if not updated_data.title and metadata and hasattr(metadata, 'title') and metadata.title:
            updated_data.title = metadata.title
            logger.debug(f"📝 从处理器结果更新title: {metadata.title}")
            
        if not updated_data.authors and metadata and hasattr(metadata, 'authors') and metadata.authors:
            updated_data.authors = metadata.authors
            logger.debug(f"👥 从处理器结果更新authors: {len(metadata.authors)} 个作者")
            
        if not updated_data.year and metadata and hasattr(metadata, 'year') and metadata.year:
            updated_data.year = metadata.year
            logger.debug(f"📅 从处理器结果更新year: {metadata.year}")
            
        if not updated_data.venue and metadata and hasattr(metadata, 'journal') and metadata.journal:
            updated_data.venue = metadata.journal
            logger.debug(f"📍 从处理器结果更新venue: {metadata.journal}")
            
        # 从new_identifiers中更新标识符
        if result.new_identifiers:
            for identifier in result.new_identifiers:
                if hasattr(identifier, 'doi') and identifier.doi and not updated_data.doi:
                    updated_data.doi = identifier.doi
                    logger.debug(f"🔗 从处理器结果更新DOI: {identifier.doi}")
                elif hasattr(identifier, 'arxiv_id') and identifier.arxiv_id and not updated_data.arxiv_id:
                    updated_data.arxiv_id = identifier.arxiv_id
                    logger.debug(f"🔗 从处理器结果更新ArXiv ID: {identifier.arxiv_id}")
                elif hasattr(identifier, 'pmid') and identifier.pmid and not updated_data.pmid:
                    updated_data.pmid = identifier.pmid
                    logger.debug(f"🔗 从处理器结果更新PMID: {identifier.pmid}")
        
        logger.debug(f"🔄 [更新] 完成identifier_data更新")
        logger.debug(f"  📖 更新后title: {updated_data.title[:50] if updated_data.title else 'None'}{'...' if updated_data.title and len(updated_data.title) > 50 else ''}")
        logger.debug(f"  👥 更新后authors: {len(updated_data.authors) if updated_data.authors else 0} 个")
        logger.debug(f"  🔗 更新后doi: {updated_data.doi or 'None'}")
        logger.debug(f"  📄 更新后arxiv_id: {updated_data.arxiv_id or 'None'}")
        
        return updated_data

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
                    logger.debug(f"[智能路由] ✅ 处理器可用: {name}")
                else:
                    logger.debug(f"[智能路由] 处理器无法处理: {name}")
            except KeyError:
                logger.warning(f"[智能路由] 处理器未注册: {name}")
            except Exception as e:
                logger.warning(f"[智能路由] 处理器实例化失败: {name}, 错误: {e}")
                
        return available
    
    def _format_value_for_debug(self, value) -> str:
        """格式化值用于调试输出"""
        if value is None:
            return "None"
        elif isinstance(value, str):
            return f"'{value[:50]}{'...' if len(value) > 50 else ''}'"
        elif isinstance(value, list):
            return f"[{len(value)} items]"
        elif isinstance(value, dict):
            return f"{{{len(value)} keys}}"
        else:
            return str(value)[:50]
