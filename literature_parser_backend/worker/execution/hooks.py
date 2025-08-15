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
        if metadata.doi:
            doi_matches = await self.dao.find_by_doi(metadata.doi)
            duplicates.extend([lit.lid for lit in doi_matches if lit.lid != current_id])
        
        # 基于标题+作者查重 (简化版)
        if metadata.title and metadata.authors:
            title_matches = await self.dao.find_by_fuzzy_title(metadata.title, threshold=0.9)
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
        self.dao = dao
    
    async def execute(self, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行别名创建"""
        try:
            literature_id = context.get('literature_id')
            metadata = context.get('metadata')
            url_info = context.get('url_info', {})
            
            if not literature_id:
                return {'status': 'skipped', 'reason': 'no_literature_id'}
            
            logger.info(f"🏷️ [Hook] 自动别名创建开始: {literature_id}")
            
            aliases_created = []
            
            # DOI别名
            if metadata and metadata.doi:
                await self._create_doi_alias(literature_id, metadata.doi)
                aliases_created.append(f"DOI:{metadata.doi}")
            
            # URL别名
            if url_info.get('url'):
                await self._create_url_alias(literature_id, url_info['url'])
                aliases_created.append(f"URL:{url_info['url']}")
            
            # ArXiv别名
            if metadata and hasattr(metadata, 'arxiv_id') and metadata.arxiv_id:
                await self._create_arxiv_alias(literature_id, metadata.arxiv_id)
                aliases_created.append(f"ArXiv:{metadata.arxiv_id}")
            
            logger.info(f"✅ [Hook] 别名创建完成: {len(aliases_created)} 个别名")
            
            return {
                'status': 'completed',
                'aliases_created': aliases_created,
                'count': len(aliases_created)
            }
            
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
        if metadata.doi:
            score += 15
        if hasattr(metadata, 'arxiv_id') and metadata.arxiv_id:
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
            QualityAssessmentHook(self.dao)
        ]
        
        for hook in hooks:
            self.register_hook(hook)
    
    def register_hook(self, hook: Hook):
        """注册Hook"""
        self.hooks[hook.name] = hook
        
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
        
        # 统计执行结果
        successful = len([r for r in hook_results if r.get('status') == 'completed'])
        logger.info(f"✅ 事件 {event} 执行完成: {successful}/{len(hooks)} Hook成功")
        
        return {
            'event': event,
            'results': hook_results,
            'summary': {
                'total_hooks': len(hooks),
                'successful': successful,
                'failed': len(hooks) - successful
            }
        }
    
    async def _execute_hook_safe(self, hook: Hook, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """安全执行Hook (捕获异常)"""
        try:
            return await hook.execute(event, context)
        except Exception as e:
            logger.error(f"❌ Hook {hook.name} 执行失败: {e}")
            return {'status': 'failed', 'error': str(e)}
