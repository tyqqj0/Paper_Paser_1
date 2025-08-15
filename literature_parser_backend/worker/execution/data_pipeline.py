"""
数据管道 - 统一的数据库操作和Hook系统

负责：
1. 状态检查 - 判断数据是否可以处理
2. 去重检查 - 统一的去重逻辑 
3. 数据写入 - 统一的数据库操作
4. Hook触发 - 事件驱动的后处理
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class DataEvent(Enum):
    """数据事件类型"""
    METADATA_EXTRACTED = "metadata_extracted"
    DUPLICATE_FOUND = "duplicate_found"
    LITERATURE_CREATED = "literature_created"
    IDENTIFIERS_UPDATED = "identifiers_updated"


class DataPipeline:
    """数据管道 - 统一的数据处理流程"""
    
    def __init__(self, dao):
        self.dao = dao
        self.hooks = []  # Hook列表
        
    async def process_data(self, raw_data: Dict[str, Any], source_data: Dict[str, Any], 
                          mapping_result: Optional[Dict], route_info: Dict, task_id: str) -> Dict[str, Any]:
        """
        统一的数据处理入口
        
        流程：原始数据 → 状态检查 → 去重检查 → 数据写入/返回重复
        """
        logger.info(f"📋 [数据管道] 开始处理数据，任务: {task_id}")
        
        try:
            # 阶段1: 状态检查 - 判断数据是否可以处理
            if not self._can_process_data(raw_data):
                return {
                    'status': 'failed',
                    'error': 'Data quality insufficient for processing',
                    'data_quality': self._evaluate_data_quality(raw_data)
                }
            
            # 阶段2: 构建标准化的文献数据
            literature_data = await self._build_literature_data(raw_data, source_data, mapping_result)
            
            # 阶段3: 统一去重检查
            duplicate_result = await self._unified_deduplication(literature_data, task_id)
            if duplicate_result['is_duplicate']:
                logger.info(f"🔍 [数据管道] 发现重复文献: {duplicate_result['existing_lid']}")
                
                # 触发重复发现事件
                await self._trigger_event(DataEvent.DUPLICATE_FOUND, {
                    'existing_lid': duplicate_result['existing_lid'],
                    'new_source': source_data,
                    'task_id': task_id
                })
                
                return {
                    'status': 'completed',
                    'result_type': 'duplicate',
                    'literature_id': duplicate_result['existing_lid'],
                    'duplicate_reason': duplicate_result['reason']
                }
            
            # 阶段4: 写入新文献数据
            new_literature = await self._create_literature(literature_data, task_id)
            
            # 阶段5: 触发创建完成事件
            await self._trigger_event(DataEvent.LITERATURE_CREATED, {
                'literature': new_literature,
                'source_data': source_data,
                'task_id': task_id
            })
            
            logger.info(f"✅ [数据管道] 文献创建完成: {new_literature['lid']}")
            
            return {
                'status': 'completed',
                'result_type': 'created', 
                'literature_id': new_literature['lid'],
                'processor_used': raw_data.get('processor_used'),
                'confidence': raw_data.get('confidence')
            }
            
        except Exception as e:
            logger.error(f"❌ [数据管道] 处理失败: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'fallback_to_legacy': True
            }
    
    def _can_process_data(self, raw_data: Dict[str, Any]) -> bool:
        """状态检查 - 判断数据是否可以处理"""
        
        # 🔧 防护性检查
        if not raw_data or not isinstance(raw_data, dict):
            logger.warning(f"[数据管道] raw_data为空或不是字典: {type(raw_data)}")
            return False
        
        # 基本成功检查
        if not raw_data.get('success'):
            logger.warning(f"[数据管道] 处理器标记为失败: {raw_data.get('error', 'Unknown error')}")
            return False
        
        # 元数据质量检查
        metadata = raw_data.get('metadata')
        if not metadata:
            logger.warning(f"[数据管道] 没有元数据")
            return False
        
        # 检查标题 - MetadataModel对象应该有title属性
        try:
            title = getattr(metadata, 'title', None)
            if not title or title in ['Unknown Title', 'Processing...']:
                logger.warning(f"[数据管道] 标题无效: {title}")
                return False
            
        except Exception as e:
            logger.warning(f"[数据管道] 标题检查异常: {e}, metadata类型: {type(metadata)}")
            return False
        
        logger.debug(f"[数据管道] 数据质量检查通过: {metadata.title}")
        return True
    
    def _evaluate_data_quality(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """评估数据质量"""
        # 🔧 防护性检查
        if not raw_data or not isinstance(raw_data, dict):
            return {'score': 0, 'issues': ['Invalid raw_data']}
        
        metadata = raw_data.get('metadata')
        if not metadata:
            return {'score': 0, 'issues': ['No metadata']}
        
        score = 0
        issues = []
        
        # 标题检查 (30分)
        title = getattr(metadata, 'title', None)
        if title and title not in ['Unknown Title', 'Processing...']:
            score += 30
        else:
            issues.append('Missing or invalid title')
        
        # 作者检查 (25分)
        authors = getattr(metadata, 'authors', None)
        if authors and len(authors) > 0:
            score += 25
        else:
            issues.append('Missing authors')
        
        # 年份检查 (20分)
        year = getattr(metadata, 'year', None)
        if year:
            score += 20
        else:
            issues.append('Missing year')
        
        # 期刊检查 (15分)
        journal = getattr(metadata, 'journal', None)
        if journal:
            score += 15
        else:
            issues.append('Missing journal')
        
        # 摘要检查 (10分)
        abstract = getattr(metadata, 'abstract', None)
        if abstract:
            score += 10
        else:
            issues.append('Missing abstract')
        
        return {'score': score, 'issues': issues}
    
    async def _build_literature_data(self, raw_data: Dict, source_data: Dict, mapping_result: Optional[Dict]) -> Dict:
        """构建标准化的文献数据"""
        
        # 🔧 防护性检查：确保raw_data不为None
        if not raw_data:
            raise ValueError("raw_data cannot be None")
        
        metadata = raw_data.get('metadata')
        new_identifiers = raw_data.get('new_identifiers') or {}
        
        # 🔧 确保source_data和mapping_result不为None
        source_data = source_data or {}
        mapping_result = mapping_result or {}
        
        # 构建标识符
        identifiers = {
            'doi': source_data.get('doi') or new_identifiers.get('doi'),
            'arxiv_id': source_data.get('arxiv_id') or new_identifiers.get('arxiv_id'),
            'pmid': source_data.get('pmid') or new_identifiers.get('pmid'),
            'url': source_data.get('url')
        }
        
        # 从URL映射结果补充标识符
        if mapping_result:
            if mapping_result.get('doi') and not identifiers['doi']:
                identifiers['doi'] = mapping_result['doi']
            if mapping_result.get('arxiv_id') and not identifiers['arxiv_id']:
                identifiers['arxiv_id'] = mapping_result['arxiv_id']

        
        return {
            'identifiers': identifiers,
            'metadata': metadata,
            'source_data': source_data,
            'processor_info': {
                'processor_used': raw_data.get('processor_used'),
                'confidence': raw_data.get('confidence')
            }
        }
    
    async def _unified_deduplication(self, literature_data: Dict, task_id: str) -> Dict[str, Any]:
        """统一去重检查 - 替代原有的5次去重"""
        
        # 🔧 防护性检查
        if not literature_data or not isinstance(literature_data, dict):
            logger.warning(f"[数据管道] literature_data无效: {type(literature_data)}")
            return {'is_duplicate': False}
        
        identifiers = literature_data.get('identifiers', {})
        metadata = literature_data.get('metadata')
        
        if not metadata:
            logger.warning(f"[数据管道] 没有元数据，跳过去重检查")
            return {'is_duplicate': False}
        
        logger.info(f"🔍 [数据管道] 开始统一去重检查，任务: {task_id}")
        
        try:
            # 优先级1: DOI去重 (最可靠)
            if identifiers.get('doi'):
                existing = await self.dao.find_by_doi(identifiers['doi'])
                if existing:
                    return {
                        'is_duplicate': True,
                        'existing_lid': existing.lid,
                        'reason': f"DOI重复: {identifiers['doi']}"
                    }
            
            # 优先级2: ArXiv ID去重
            if identifiers.get('arxiv_id'):
                existing = await self.dao.find_by_arxiv_id(identifiers['arxiv_id'])
                if existing:
                    return {
                        'is_duplicate': True,
                        'existing_lid': existing.lid,
                        'reason': f"ArXiv ID重复: {identifiers['arxiv_id']}"
                    }
            
            # 优先级3: 标题+作者去重 (模糊匹配)
            if hasattr(metadata, 'title') and metadata.title:
                candidates = await self.dao.find_by_title_fuzzy(metadata.title, limit=5)
                for candidate in candidates:
                    if candidate and candidate.metadata and candidate.metadata.title:
                        if self._is_title_match(metadata.title, candidate.metadata.title):
                            # 进一步检查作者匹配
                            metadata_authors = getattr(metadata, 'authors', None)
                            candidate_authors = getattr(candidate.metadata, 'authors', None)
                            if self._is_author_match(metadata_authors, candidate_authors):
                                return {
                                    'is_duplicate': True,
                                    'existing_lid': candidate.lid,
                                    'reason': f"标题+作者重复: {metadata.title[:50]}..."
                                }
            
            logger.info(f"✅ [数据管道] 去重检查完成，无重复")
            return {'is_duplicate': False}
            
        except Exception as e:
            logger.error(f"❌ [数据管道] 去重检查异常: {e}")
            # 去重失败时保守处理，返回无重复
            return {'is_duplicate': False}
    
    def _is_title_match(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """标题匹配检查"""
        if not title1 or not title2:
            return False
        
        # 简化的标题匹配 (可以后续优化)
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
        return similarity >= threshold
    
    def _is_author_match(self, authors1, authors2, threshold: float = 0.6) -> bool:
        """作者匹配检查"""
        # 🔧 防护性检查
        if not authors1 or not authors2:
            return False
        
        # 确保是列表
        if not isinstance(authors1, list):
            return False
        if not isinstance(authors2, list):
            return False
        
        try:
            # 提取作者姓名
            names1 = set()
            for author in authors1:
                if isinstance(author, dict):
                    name = author.get('name', '')
                elif isinstance(author, str):
                    name = author
                else:
                    # 如果author有name属性
                    name = getattr(author, 'name', '')
                
                if name:
                    names1.add(name.strip())
            
            names2 = set()
            for author in authors2:
                if isinstance(author, dict):
                    name = author.get('name', '')
                elif isinstance(author, str):
                    name = author
                else:
                    # 如果author有name属性
                    name = getattr(author, 'name', '')
                
                if name:
                    names2.add(name.strip())
            
            # 计算交集比例
            if len(names1) == 0 or len(names2) == 0:
                return False
            
            intersection = len(names1 & names2)
            min_authors = min(len(names1), len(names2))
            similarity = intersection / min_authors
            
            return similarity >= threshold
            
        except Exception as e:
            logger.warning(f"[数据管道] 作者匹配检查异常: {e}")
            return False
    
    async def _create_literature(self, literature_data: Dict, task_id: str) -> Dict[str, Any]:
        """创建新文献 - 统一的数据库写入"""
        
        logger.info(f"📝 [数据管道] 创建新文献，任务: {task_id}")
        
        # 生成LID
        try:
            from ...services.lid_generator import LIDGenerator
            lid_generator = LIDGenerator()
            lid = lid_generator.generate_lid(literature_data['metadata'])
        except ImportError:
            # 如果导入失败，生成一个临时ID
            import uuid
            lid = f"temp-{task_id[:8]}-{str(uuid.uuid4())[:8]}"
            logger.warning(f"[数据管道] LID生成器导入失败，使用临时ID: {lid}")
        except Exception as e:
            # 如果生成失败，使用临时ID
            import uuid
            lid = f"temp-{task_id[:8]}-{str(uuid.uuid4())[:8]}"
            logger.error(f"[数据管道] LID生成失败: {e}，使用临时ID: {lid}")
        
        # 创建占位符
        identifiers_model = self._build_identifiers_model(literature_data['identifiers'])
        literature_id = await self.dao.create_placeholder(task_id, identifiers_model)
        
        # 构建完整的文献模型
        literature_model = self._build_literature_model(literature_data, lid, task_id)
        
        # 最终化文献
        await self.dao.finalize_literature(literature_id, literature_model)
        
        logger.info(f"✅ [数据管道] 文献创建完成: {lid}")
        
        return {
            'lid': lid,
            'internal_id': literature_id,
            'metadata': literature_data['metadata'],
            'identifiers': literature_data['identifiers']
        }
    
    def _build_identifiers_model(self, identifiers: Dict):
        """构建标识符模型"""
        try:
            from ...models.literature import IdentifiersModel
            return IdentifiersModel(
                doi=identifiers.get('doi'),
                arxiv_id=identifiers.get('arxiv_id'),
                pmid=identifiers.get('pmid')
            )
        except ImportError as e:
            logger.error(f"[数据管道] 无法导入IdentifiersModel: {e}")
            # 返回一个简单的字典作为备选
            return {
                'doi': identifiers.get('doi'),
                'arxiv_id': identifiers.get('arxiv_id'),
                'pmid': identifiers.get('pmid')
            }
    
    def _build_literature_model(self, literature_data: Dict, lid: str, task_id: str):
        """构建文献模型"""
        try:
            from ...models.literature import LiteratureModel, ContentModel, TaskInfoModel
            from datetime import datetime
            
            # 任务信息
            task_info = TaskInfoModel(
                task_id=task_id,
                status="completed",
                created_at=datetime.now(),
                completed_at=datetime.now()
            )
            
            # 构建文献模型
            return LiteratureModel(
                lid=lid,
                task_info=task_info,
                identifiers=self._build_identifiers_model(literature_data['identifiers']),
                metadata=literature_data['metadata'],
                content=ContentModel(),  # 空内容，后续填充
                references=[]  # 引用信息后续处理
            )
        except ImportError as e:
            logger.error(f"[数据管道] 无法导入文献模型: {e}")
            # 返回简化的字典结构
            from datetime import datetime
            return {
                'lid': lid,
                'task_id': task_id,
                'status': 'completed',
                'created_at': datetime.now(),
                'identifiers': literature_data['identifiers'],
                'metadata': literature_data['metadata'],
                'content': {},
                'references': []
            }
    
    async def _trigger_event(self, event: DataEvent, context: Dict[str, Any]):
        """触发事件 - Hook系统的入口"""
        logger.info(f"🎯 [数据管道] 触发事件: {event.value}")
        
        # 这里可以扩展Hook系统
        # 目前简化处理，后续可以添加具体的Hook实现
        
        if event == DataEvent.DUPLICATE_FOUND:
            await self._handle_duplicate_found(context)
        elif event == DataEvent.LITERATURE_CREATED:
            await self._handle_literature_created(context)
    
    async def _handle_duplicate_found(self, context: Dict[str, Any]):
        """处理重复发现事件"""
        # 可以在这里添加别名映射等逻辑
        logger.info(f"🔗 [数据管道] 处理重复发现: {context['existing_lid']}")
    
    async def _handle_literature_created(self, context: Dict[str, Any]):
        """处理文献创建事件"""
        # 可以在这里添加别名创建、关系建立等逻辑
        logger.info(f"🆕 [数据管道] 处理文献创建: {context['literature']['lid']}")
