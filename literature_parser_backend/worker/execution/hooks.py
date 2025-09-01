"""
Hook系统 - 自动化数据处理钩子

实现事件驱动的自动查重、别名创建、质量评估等后处理逻辑。
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from abc import ABC, abstractmethod

from ...models.literature import MetadataModel
from ...db.dao import LiteratureDAO

logger = logging.getLogger(__name__)


class Hook(ABC):
    """Hook基类 - 所有Hook都继承此类"""
    
    def __init__(self):
        self.hook_manager = None
    
    def set_hook_manager(self, hook_manager):
        """设置HookManager引用，用于触发级联事件"""
        self.hook_manager = hook_manager
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Hook名称"""
        pass
    
    @property
    @abstractmethod
    def triggers(self) -> List[str]:
        """触发事件列表"""
        pass
    
    @abstractmethod
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行Hook逻辑"""
        pass


class DeduplicationHook(Hook):
    """自动查重Hook - 当新元数据可用时自动检查重复"""
    
    @property
    def name(self) -> str:
        return "auto_deduplication"
    
    @property
    def triggers(self) -> List[str]:
        return ["metadata_updated", "literature_created"]
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行自动查重"""
        try:
            literature_id = context.get('literature_id')
            metadata = context.get('metadata')
            
            if not literature_id or not metadata:
                return {'status': 'skipped', 'reason': 'insufficient_data'}
            
            logger.info(f"🔍 [Hook] 自动查重开始: {literature_id}")
            
            # 执行查重逻辑
            duplicates = await self._find_duplicates(metadata, literature_id)
            
            if duplicates:
                # 发现重复，合并处理
                merged_result = await self._handle_duplicates(literature_id, duplicates, context)
                logger.info(f"✅ [Hook] 查重完成，发现 {len(duplicates)} 个重复项")
                return {
                    'status': 'completed',
                    'action': 'merged',
                    'duplicates_found': len(duplicates),
                    'result': merged_result
                }
            else:
                logger.info(f"✅ [Hook] 查重完成，未发现重复项")
                return {'status': 'completed', 'action': 'none', 'duplicates_found': 0}
                
        except Exception as e:
            logger.error(f"❌ [Hook] 自动查重失败: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _find_duplicates(self, metadata: MetadataModel, current_id: str) -> List[str]:
        """查找重复项"""
        duplicates = []
        
        # 基于DOI查重
        if hasattr(metadata, 'identifiers') and metadata.identifiers and hasattr(metadata.identifiers, 'doi') and metadata.identifiers.doi:
            doi_matches = await self.dao.find_by_doi(metadata.identifiers.doi)
            duplicates.extend([lit.lid for lit in doi_matches if lit.lid != current_id])
        
        # 基于标题+作者查重 (简化版)
        if metadata.title and metadata.authors:
            title_matches = await self.dao.find_by_title_fuzzy(metadata.title, threshold=0.9)
            for match in title_matches:
                if match.lid != current_id and match.lid not in duplicates:
                    # 简单的作者匹配检查
                    if self._authors_match(metadata.authors, match.authors):
                        duplicates.append(match.lid)
        
        return duplicates
    
    def _authors_match(self, authors1: List[Dict], authors2: List[Dict], threshold: float = 0.7) -> bool:
        """简单的作者匹配算法"""
        if not authors1 or not authors2:
            return False
        
        # 提取作者姓名
        names1 = {author.get('name', '') for author in authors1}
        names2 = {author.get('name', '') for author in authors2}
        
        # 计算交集比例
        intersection = len(names1 & names2)
        union = len(names1 | names2)
        
        if union == 0:
            return False
            
        similarity = intersection / union
        return similarity >= threshold
    
    async def _handle_duplicates(self, literature_id: str, duplicates: List[str], context: Dict[str, Any]) -> Dict:
        """处理发现的重复项"""
        # 简化处理：选择第一个重复项作为主项，删除当前项
        if duplicates:
            primary_id = duplicates[0]
            
            # 将别名添加到主项
            # 这里应该调用DAO的方法来处理别名合并
            logger.info(f"📋 [Hook] 将 {literature_id} 合并到 {primary_id}")
            
            return {
                'primary_id': primary_id,
                'merged_ids': [literature_id],
                'action': 'merged_to_existing'
            }
        
        return {}


class AliasCreationHook(Hook):
    """别名创建Hook - 自动为新文献创建各种别名"""
    
    @property
    def name(self) -> str:
        return "auto_alias_creation"
    
    @property
    def triggers(self) -> List[str]:
        return ["literature_created", "metadata_updated"]
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行别名创建 - 实现完整的别名映射逻辑"""
        try:
            literature_id = context.get('literature_id')
            
            if not literature_id:
                return {'status': 'skipped', 'reason': 'Missing literature_id'}
            
            logger.info(f"🏷️ [Hook] 开始创建别名: {literature_id}")
            
            # 获取当前文献
            literature = await self.dao.find_by_lid(literature_id)
            if not literature:
                return {'status': 'skipped', 'reason': 'Literature not found'}
            
            # 🎯 使用完整的别名映射逻辑
            try:
                from ...db.alias_dao import AliasDAO
                from ...models.alias import AliasType, extract_aliases_from_source
                
                # 创建别名DAO
                alias_dao = AliasDAO(database=self.dao.driver if hasattr(self.dao, 'driver') else None)
                
                # 从上下文获取源数据
                source_data = context.get('source_data', {})
                
                # 提取源别名
                source_aliases = extract_aliases_from_source(source_data)
                logger.info(f"🏷️ [Hook] 从源数据中找到 {len(source_aliases)} 个别名")
                
                # 添加从文献标识符中提取的别名
                literature_aliases = {}
                
                if literature.identifiers:
                    if hasattr(literature.identifiers, 'doi') and literature.identifiers.doi:
                        literature_aliases[AliasType.DOI] = literature.identifiers.doi
                    
                    if hasattr(literature.identifiers, 'arxiv_id') and literature.identifiers.arxiv_id:
                        literature_aliases[AliasType.ARXIV] = literature.identifiers.arxiv_id
                        
                    if hasattr(literature.identifiers, 'pmid') and literature.identifiers.pmid:
                        literature_aliases[AliasType.PMID] = literature.identifiers.pmid
                
                # 添加内容URL别名
                if literature.content:
                    if hasattr(literature.content, 'pdf_url') and literature.content.pdf_url:
                        literature_aliases[AliasType.PDF_URL] = literature.content.pdf_url
                        
                    if hasattr(literature.content, 'source_page_url') and literature.content.source_page_url:
                        literature_aliases[AliasType.SOURCE_PAGE] = literature.content.source_page_url
                
                # 添加标题别名（用于基于标题的查找）
                if literature.metadata and hasattr(literature.metadata, 'title') and literature.metadata.title:
                    literature_aliases[AliasType.TITLE] = literature.metadata.title
                
                # 合并所有别名
                all_aliases = {**source_aliases, **literature_aliases}
                logger.info(f"🏷️ [Hook] 总共 {len(all_aliases)} 个别名待创建: {literature_id}")
                
                # 批量创建映射
                if all_aliases:
                    task_id = context.get('task_id', 'unknown')
                    created_ids = await alias_dao.batch_create_mappings(
                        lid=literature_id,
                        mappings=all_aliases,
                        confidence=1.0,
                        metadata={
                            "source": "literature_creation",
                            "task_id": task_id,
                            "created_from": "hook_automatic_mapping"
                        }
                    )
                    
                    logger.info(f"✅ [Hook] 成功创建 {len(created_ids)} 个别名映射: {literature_id}")
                    
                    # 格式化别名列表用于日志
                    alias_summary = []
                    for alias_type, value in all_aliases.items():
                        alias_summary.append(f"{alias_type.value}:{value[:50]}...")
                    
                    return {
                        'status': 'completed',
                        'aliases_created': alias_summary,
                        'count': len(created_ids),
                        'total_aliases': len(all_aliases)
                    }
                else:
                    logger.warning(f"🏷️ [Hook] 没有找到别名需要创建: {literature_id}")
                    return {
                        'status': 'completed',
                        'aliases_created': [],
                        'count': 0,
                        'reason': 'No aliases found'
                    }
                    
            except ImportError:
                logger.error(f"❌ [Hook] 无法导入别名相关模块")
                return {'status': 'failed', 'error': 'Alias modules not available'}
            
        except Exception as e:
            logger.error(f"❌ [Hook] 别名创建失败: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _create_doi_alias(self, literature_id: str, doi: str):
        """创建DOI别名"""
        # 这里应该调用DAO的方法创建DOI别名
        logger.debug(f"📋 创建DOI别名: {literature_id} -> {doi}")
    
    async def _create_url_alias(self, literature_id: str, url: str):
        """创建URL别名"""
        # 这里应该调用DAO的方法创建URL别名
        logger.debug(f"📋 创建URL别名: {literature_id} -> {url}")
    
    async def _create_arxiv_alias(self, literature_id: str, arxiv_id: str):
        """创建ArXiv别名"""
        # 这里应该调用DAO的方法创建ArXiv别名
        logger.debug(f"📋 创建ArXiv别名: {literature_id} -> {arxiv_id}")


class QualityAssessmentHook(Hook):
    """质量评估Hook - 自动评估文献元数据质量"""
    
    @property
    def name(self) -> str:
        return "auto_quality_assessment"
    
    @property
    def triggers(self) -> List[str]:
        return ["metadata_updated"]
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行质量评估"""
        try:
            metadata = context.get('metadata')
            literature_id = context.get('literature_id')
            
            if not metadata:
                return {'status': 'skipped', 'reason': 'no_metadata'}
            
            logger.info(f"📊 [Hook] 质量评估开始: {literature_id}")
            
            # 计算质量分数
            quality_score = self._calculate_quality_score(metadata)
            quality_level = self._get_quality_level(quality_score)
            
            # 更新质量信息到数据库
            await self._update_quality_info(literature_id, quality_score, quality_level)
            
            logger.info(f"✅ [Hook] 质量评估完成: {quality_score}/100 ({quality_level})")
            
            return {
                'status': 'completed',
                'quality_score': quality_score,
                'quality_level': quality_level
            }
            
        except Exception as e:
            logger.error(f"❌ [Hook] 质量评估失败: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    def _calculate_quality_score(self, metadata: MetadataModel) -> int:
        """计算质量分数 (0-100)"""
        score = 0
        
        # 基础信息 (40分)
        if metadata.title:
            score += 20
        if metadata.authors and len(metadata.authors) > 0:
            score += 20
        
        # 标识符 (30分)
        if hasattr(metadata, 'identifiers') and metadata.identifiers:
            if hasattr(metadata.identifiers, 'doi') and metadata.identifiers.doi:
                score += 15
            if hasattr(metadata.identifiers, 'arxiv_id') and metadata.identifiers.arxiv_id:
                score += 10
        if metadata.year:
            score += 5
        
        # 详细信息 (30分)
        if metadata.abstract and len(metadata.abstract) > 100:
            score += 15
        if metadata.journal:
            score += 10
        if metadata.keywords and len(metadata.keywords) > 0:
            score += 5
        
        return min(score, 100)
    
    def _get_quality_level(self, score: int) -> str:
        """获取质量等级"""
        if score >= 80:
            return "high"
        elif score >= 60:
            return "medium"
        elif score >= 40:
            return "low"
        else:
            return "poor"
    
    async def _update_quality_info(self, literature_id: str, score: int, level: str):
        """更新质量信息到数据库"""
        # 这里应该调用DAO的方法更新质量信息
        logger.debug(f"📋 更新质量信息: {literature_id} -> {score} ({level})")


class HookManager:
    """Hook管理器 - 管理所有Hook的注册和执行"""
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
        self.hooks: Dict[str, Hook] = {}
        self.event_hooks: Dict[str, List[Hook]] = {}
        
        # 注册默认Hook
        self._register_default_hooks()
    
    def _register_default_hooks(self):
        """注册默认Hook"""
        hooks = [
            DeduplicationHook(self.dao),
            AliasCreationHook(self.dao),
            QualityAssessmentHook(self.dao),
            # 🆕 新增关系数据处理Hook
            # ReferencesFetchHook(self.dao),
            CitationResolverHook(self.dao),
            UnresolvedNodeUpgradeHook(self.dao)
        ]
        
        for hook in hooks:
            self.register_hook(hook)
    
    def register_hook(self, hook: Hook):
        """注册Hook"""
        self.hooks[hook.name] = hook
        
        # 为Hook设置HookManager引用，以便触发级联事件
        if hasattr(hook, 'set_hook_manager'):
            hook.set_hook_manager(self)
        
        # 建立事件到Hook的映射
        for event in hook.triggers:
            if event not in self.event_hooks:
                self.event_hooks[event] = []
            self.event_hooks[event].append(hook)
        
        logger.info(f"✅ 注册Hook: {hook.name} (触发事件: {hook.triggers})")
    
    async def trigger_event(self, event: str, context: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """触发事件，执行相关Hook"""
        if event not in self.event_hooks:
            logger.debug(f"🔍 事件 {event} 没有对应的Hook")
            return {'event': event, 'results': []}
        
        hooks = self.event_hooks[event]
        logger.info(f"🚀 触发事件 {event}, 执行 {len(hooks)} 个Hook")
        
        # 并行执行所有相关Hook
        tasks = []
        for hook in hooks:
            task = asyncio.create_task(self._execute_hook_safe(hook, event, context))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        hook_results = []
        next_events = []  # 收集需要触发的下一个事件
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                hook_results.append({
                    'hook': hooks[i].name,
                    'status': 'failed',
                    'error': str(result)
                })
            else:
                hook_results.append({
                    'hook': hooks[i].name,
                    **result
                })
                
                # 检查是否有下一个事件需要触发
                if result.get('next_event'):
                    next_events.append(result['next_event'])
        
        # 统计执行结果
        successful = len([r for r in hook_results if r.get('status') == 'completed'])
        logger.info(f"✅ 事件 {event} 执行完成: {successful}/{len(hooks)} Hook成功")
        
        # 🆕 触发级联事件
        cascade_results = []
        for next_event in set(next_events):  # 去重
            logger.info(f"🔗 触发级联事件: {next_event}")
            cascade_result = await self.trigger_event(next_event, context)
            cascade_results.append(cascade_result)
        
        result = {
            'event': event,
            'results': hook_results,
            'summary': {
                'total_hooks': len(hooks),
                'successful': successful,
                'failed': len(hooks) - successful
            }
        }
        
        # 如果有级联事件，也包含在结果中
        if cascade_results:
            result['cascade_events'] = cascade_results
        
        return result
    
    async def _execute_hook_safe(self, hook: Hook, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """安全执行Hook (捕获异常)"""
        try:
            return await hook.execute(event, context)
        except Exception as e:
            logger.error(f"❌ Hook {hook.name} 执行失败: {e}")
            return {'status': 'failed', 'error': str(e)}


# =================== 🆕 新增关系数据处理Hook ===================

# class ReferencesFetchHook(Hook):
#     """引用文献获取Hook    未启用"""
    
#     @property
#     def name(self) -> str:
#         return "references_fetch"
    
#     @property
#     def triggers(self) -> List[str]:
#         return ["metadata_updated"]
    
#     def __init__(self, dao: LiteratureDAO):
#         super().__init__()
#         self.dao = dao
    
#     async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
#         """获取引用文献"""
#         try:
#             literature_id = context.get('literature_id')
#             metadata = context.get('metadata')
            
#             if not literature_id or not metadata:
#                 return {'status': 'skipped', 'reason': 'Missing literature_id or metadata'}
            
#             logger.info(f"📚 [Hook] 开始获取引用文献: {literature_id}")
            
#             # 🎯 使用原有的ReferencesFetcher逻辑
#             try:
#                 from ..references_fetcher import ReferencesFetcher
#                 from ...settings import Settings
                
#                 settings = Settings()
#                 references_fetcher = ReferencesFetcher(settings)
                
#                 # 构建标识符字典
#                 identifiers = {}
#                 if metadata:
#                     if hasattr(metadata, 'identifiers') and metadata.identifiers:
#                         if hasattr(metadata.identifiers, 'doi') and metadata.identifiers.doi:
#                             identifiers['doi'] = metadata.identifiers.doi
#                         if hasattr(metadata.identifiers, 'arxiv_id') and metadata.identifiers.arxiv_id:
#                             identifiers['arxiv_id'] = metadata.identifiers.arxiv_id
                
#                 logger.info(f"📚 [Hook] 使用标识符获取引用: {identifiers}")
                
#                 # 使用瀑布流方法获取引用
#                 if identifiers:
#                     references, raw_data = references_fetcher.fetch_references_waterfall(
#                         identifiers=identifiers,
#                         pdf_content=None  # 暂时不传入PDF内容
#                     )
                    
#                     if references:
#                         # 更新文献的引用信息（如果DAO支持此方法）
#                         try:
#                             if hasattr(self.dao, 'update_literature_references'):
#                                 await self.dao.update_literature_references(literature_id, references)
#                         except Exception as e:
#                             logger.warning(f"更新文献引用失败: {e}")
                        
#                         # 🎯 触发引用获取完成事件
#                         # 将引用数据添加到上下文中，供CitationResolverHook使用
#                         context.update({
#                             'references': references,
#                             'raw_references_data': raw_data,
#                             'source_identifiers': identifiers
#                         })
                        
#                         logger.info(f"✅ [Hook] 引用获取完成: {len(references)} 个引用")
                        
#                         # 🔄 手动触发级联事件
#                         if hasattr(self, 'hook_manager') and self.hook_manager:
#                             try:
#                                 await self.hook_manager.trigger_event('references_fetched', context)
#                                 logger.info(f"🔄 [Hook] 已触发 references_fetched 事件")
#                             except Exception as e:
#                                 logger.warning(f"触发级联事件失败: {e}")
                        
#                         return {
#                             'status': 'completed',
#                             'references_count': len(references),
#                             'identifiers_used': identifiers,
#                             'cascade_triggered': True
#                         }
#                     else:
#                         logger.warning(f"⚠️ [Hook] 使用理想标识符未能获取到引用文献")
#                         return {
#                             'status': 'completed',
#                             'references_count': 0,
#                             'reason': 'No references found from sources with ideal identifiers'
#                         }
#                 else:
#                     logger.warning(f"⚠️ [Hook] 没有可用的标识符获取引用")
#                     return {
#                         'status': 'skipped',
#                         'reason': 'No valid identifiers (DOI/ArXiv) available'
#                     }
                    
#             except ImportError:
#                 logger.error(f"❌ [Hook] 无法导入ReferencesFetcher")
#                 return {'status': 'failed', 'error': 'ReferencesFetcher not available'}
                
#         except Exception as e:
#             logger.error(f"❌ [Hook] 引用获取失败: {e}")
#             return {'status': 'failed', 'error': str(e)}


class CitationResolverHook(Hook):
    """引用关系解析Hook"""
    
    @property
    def name(self) -> str:
        return "citation_resolver"
    
    @property
    def triggers(self) -> List[str]:
        return ["references_fetched", "literature_created"]
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """解析引用关系"""
        try:
            literature_id = context.get('literature_id')
            
            if not literature_id:
                return {'status': 'skipped', 'reason': 'Missing literature_id'}
            
            logger.info(f"🔗 [Hook] 开始解析引用关系: {literature_id}")
            
            # 获取文献的引用列表
            literature = await self.dao.find_by_lid(literature_id)
            if not literature or not literature.references:
                return {'status': 'skipped', 'reason': 'No references to resolve'}
            
            references = literature.references
            
            try:
                from ..citation_resolver import CitationResolver
                
                # 初始化引用解析器
                citation_resolver = CitationResolver(task_id=context.get('task_id', 'unknown'))
                await citation_resolver.initialize_with_dao(self.dao)
                
                # 解析引用关系
                resolution_result = await citation_resolver.resolve_citations_for_literature(
                    citing_literature_lid=literature_id,
                    references=references
                )
                
                stats = resolution_result.get("statistics", {})
                logger.info(f"🔗 [Hook] 引用关系解析完成: {stats.get('resolved_citations', 0)} 已解析, {stats.get('unresolved_references', 0)} 未解析")
                
                return {
                    'status': 'completed',
                    'statistics': stats,
                    'resolution_rate': stats.get('resolution_rate', 0.0)
                }
                
            except ImportError:
                logger.error(f"❌ [Hook] 无法导入CitationResolver")
                return {'status': 'failed', 'error': 'CitationResolver not available'}
                
        except Exception as e:
            logger.error(f"❌ [Hook] 引用关系解析失败: {e}")
            return {'status': 'failed', 'error': str(e)}


class UnresolvedNodeUpgradeHook(Hook):
    """未解析节点升级Hook"""
    
    @property
    def name(self) -> str:
        return "unresolved_node_upgrade"
    
    @property
    def triggers(self) -> List[str]:
        return ["literature_created"]
    
    def __init__(self, dao: LiteratureDAO):
        super().__init__()
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """升级匹配的未解析节点"""
        try:
            literature_id = context.get('literature_id')
            
            if not literature_id:
                return {'status': 'skipped', 'reason': 'Missing literature_id'}
            
            logger.info(f"⬆️ [Hook] 开始升级未解析节点: {literature_id}")
            
            # 获取新创建的文献
            literature = await self.dao.find_by_lid(literature_id)
            if not literature:
                return {'status': 'skipped', 'reason': 'Literature not found'}
            
            # 🎯 实现未解析节点升级逻辑
            # 这里需要调用原有的 _upgrade_matching_unresolved_nodes 函数逻辑
            try:
                upgraded_count = await self._upgrade_matching_unresolved_nodes(literature)
                
                logger.info(f"⬆️ [Hook] 未解析节点升级完成: {upgraded_count} 个节点已升级")
                
                return {
                    'status': 'completed',
                    'upgraded_nodes': upgraded_count
                }
                
            except Exception as e:
                logger.error(f"❌ [Hook] 节点升级逻辑失败: {e}")
                return {'status': 'failed', 'error': f'Upgrade logic failed: {str(e)}'}
                
        except Exception as e:
            logger.error(f"❌ [Hook] 未解析节点升级失败: {e}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _upgrade_matching_unresolved_nodes(self, literature) -> int:
        """升级匹配的未解析节点 (实现原有逻辑)"""
        try:
            from ...db.relationship_dao import RelationshipDAO
            
            # 创建关系DAO - 使用相同的数据库连接
            relationship_dao = RelationshipDAO(database=self.dao.driver if hasattr(self.dao, 'driver') else None)
            
            # 生成匹配候选的LID模式
            matching_patterns = []
            
            # 🎯 基于标题规范化进行智能匹配
            if literature.metadata and literature.metadata.title:
                # 使用标题规范化进行匹配查找
                try:
                    from ...utils.title_normalization import normalize_title_for_matching
                    
                    normalized_title = normalize_title_for_matching(literature.metadata.title)
                    if normalized_title:
                        logger.info(f"⬆️ [Hook] 搜索标题匹配的未解析节点: '{normalized_title[:50]}...'")
                        
                        # 直接查找数据库中匹配的未解析节点
                        async with relationship_dao._get_session() as session:
                            # 查找标题匹配的未解析节点
                            title_match_query = """
                            MATCH (u:Unresolved)
                            WHERE u.parsed_title IS NOT NULL
                            RETURN u.lid as lid, u.parsed_title as title, u.parsed_year as year
                            """
                            
                            result = await session.run(title_match_query)
                            candidate_nodes = []
                            async for record in result:
                                candidate_title = record["title"]
                                candidate_year = record["year"]
                                candidate_lid = record["lid"]
                                
                                if candidate_title:
                                    candidate_normalized = normalize_title_for_matching(candidate_title)
                                    
                                    # 🎯 匹配条件：标题相同 + 年份相同或相近(±1年)
                                    title_matches = candidate_normalized == normalized_title
                                    year_matches = True  # 默认匹配
                                    
                                    if literature.metadata.year and candidate_year:
                                        try:
                                            lit_year = int(literature.metadata.year)
                                            cand_year = int(candidate_year)
                                            # 允许±1年的差异
                                            year_matches = abs(lit_year - cand_year) <= 1
                                        except (ValueError, TypeError):
                                            year_matches = True  # 年份解析失败时不作为阻断条件
                                    
                                    if title_matches and year_matches:
                                        candidate_nodes.append({
                                            "lid": candidate_lid,
                                            "title": candidate_title,
                                            "year": candidate_year
                                        })
                                        logger.info(f"⬆️ [Hook] 找到标题匹配候选: {candidate_lid} (年份: {candidate_year} vs {literature.metadata.year})")
                            
                            # 添加匹配的候选LID
                            for candidate in candidate_nodes:
                                matching_patterns.append(candidate["lid"])
                                
                except ImportError:
                    logger.warning("⬆️ [Hook] 无法导入title_normalization，跳过标题匹配")
                except Exception as e:
                    logger.warning(f"⬆️ [Hook] 标题匹配出错: {e}")
            
            logger.info(f"⬆️ [Hook] 搜索匹配的未解析节点: {matching_patterns}")
            
            # 检查每个可能的LID并执行升级
            upgraded_count = 0
            for pattern_lid in matching_patterns:
                try:
                    # 检查是否存在这个未解析节点
                    async with relationship_dao._get_session() as session:
                        check_query = """
                        MATCH (unresolved:Unresolved {lid: $pattern_lid})
                        RETURN unresolved.lid as lid, unresolved.parsed_title as title
                        """
                        
                        result = await session.run(check_query, pattern_lid=pattern_lid)
                        record = await result.single()
                        
                        if record:
                            logger.info(f"⬆️ [Hook] 找到匹配的未解析节点: {pattern_lid} -> {record['title']}")
                            
                            # 执行升级
                            upgrade_stats = await relationship_dao.upgrade_unresolved_to_literature(
                                placeholder_lid=pattern_lid,
                                literature_lid=literature.lid
                            )
                            
                            if upgrade_stats.get("relationships_updated", 0) > 0:
                                upgraded_count += 1
                                logger.info(f"⬆️ [Hook] ✅ 升级成功 {pattern_lid} -> {literature.lid}, 更新了 {upgrade_stats['relationships_updated']} 个关系")
                            else:
                                logger.warning(f"⬆️ [Hook] ⚠️ 找到 {pattern_lid} 但没有关系需要升级")
                        
                except Exception as e:
                    logger.warning(f"⬆️ [Hook] 检查模式 {pattern_lid} 时出错: {e}")
                    # 继续检查其他模式
            
            if upgraded_count > 0:
                logger.info(f"⬆️ [Hook] ✅ 成功升级 {upgraded_count} 个未解析节点到文献 {literature.lid}")
            else:
                logger.info(f"⬆️ [Hook] 没有找到匹配的未解析节点 {literature.lid}")
            
            return upgraded_count
            
        except ImportError:
            logger.error("⬆️ [Hook] 无法导入RelationshipDAO")
            return 0
        except Exception as e:
            logger.error(f"⬆️ [Hook] 未解析节点升级出错: {e}")
            return 0
