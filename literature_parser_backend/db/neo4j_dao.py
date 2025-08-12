"""
Neo4j Data Access Objects (DAO) for literature management.

This module provides high-level database operations for literature nodes and relationships,
serving as the Neo4j equivalent of the MongoDB DAO layer.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from neo4j import AsyncDriver, AsyncSession

from ..models.literature import (
    LiteratureModel,
    LiteratureSummaryDTO,
    literature_to_summary_dto,
)
from .neo4j_connection import get_neo4j_session

logger = logging.getLogger(__name__)


class Neo4jLiteratureDAO:
    """Neo4j Data Access Object for literature operations."""
    
    def __init__(self, driver: Optional[AsyncDriver] = None):
        """
        Initialize DAO with Neo4j driver.
        
        :param driver: Neo4j driver instance (optional, uses global if None)
        """
        self.driver = driver
    
    @classmethod
    def create_from_task_driver(cls, driver: AsyncDriver) -> "Neo4jLiteratureDAO":
        """
        Create DAO instance using task-level driver.
        
        :param driver: Task-specific Neo4j driver
        :return: DAO instance using task driver
        """
        return cls(driver=driver)
    
    async def _get_session(self, **kwargs) -> AsyncSession:
        """Get Neo4j session, using task driver if available."""
        if self.driver:
            return self.driver.session(**kwargs)
        else:
            return get_neo4j_session(**kwargs)
    
    # ========== Literature CRUD Operations ==========
    
    async def create_literature(self, literature: LiteratureModel) -> str:
        """
        Create a literature node in Neo4j.
        
        :param literature: Literature model to create
        :return: LID of created literature
        """
        try:
            async with await self._get_session() as session:
                # 准备节点属性 (移除任务信息，只保留文献数据)
                node_props = {
                    "lid": literature.lid,
                    "user_id": str(literature.user_id) if literature.user_id else None,
                    "created_at": literature.created_at.isoformat(),
                    "updated_at": literature.updated_at.isoformat(),
                    
                    # 结构化数据存储为JSON属性
                    "identifiers": literature.identifiers.model_dump() if literature.identifiers else {},
                    "metadata": literature.metadata.model_dump() if literature.metadata else {},
                    "content": literature.content.model_dump() if literature.content else {},
                    
                    # 临时存储references (Phase 2会转为关系)
                    "temp_references": [ref.model_dump() for ref in literature.references] if literature.references else [],
                    
                    # 保留原始数据
                    "raw_data": literature.raw_data or {}
                }
                
                # 清理None值
                node_props = {k: v for k, v in node_props.items() if v is not None}
                
                query = """
                MERGE (lit:Literature {lid: $lid})
                SET lit += $props
                RETURN lit.lid as lid
                """
                
                result = await session.run(query, lid=literature.lid, props=node_props)
                record = await result.single()
                
                if record:
                    logger.info(f"Created Literature node with LID: {record['lid']}")
                    return record["lid"]
                else:
                    raise RuntimeError("Failed to create Literature node")
                    
        except Exception as e:
            logger.error(f"Failed to create literature {literature.lid}: {e}", exc_info=True)
            raise
    
    async def find_by_lid(self, lid: str) -> Optional[LiteratureModel]:
        """
        Find literature by LID.
        
        :param lid: Literature ID to search for
        :return: Literature model if found, None otherwise
        """
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})
                RETURN lit
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by LID {lid}: {e}")
            return None
    
    async def find_by_doi(self, doi: str) -> Optional[LiteratureModel]:
        """Find literature by DOI."""
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE lit.`identifiers.doi` = $doi
                RETURN lit
                """
                
                result = await session.run(query, doi=doi)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by DOI {doi}: {e}")
            return None
    
    async def find_by_arxiv_id(self, arxiv_id: str) -> Optional[LiteratureModel]:
        """Find literature by ArXiv ID."""
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE lit.`identifiers.arxiv_id` = $arxiv_id
                RETURN lit
                """
                
                result = await session.run(query, arxiv_id=arxiv_id)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by ArXiv ID {arxiv_id}: {e}")
            return None
    
    async def find_by_fingerprint(self, fingerprint: str) -> Optional[LiteratureModel]:
        """Find literature by content fingerprint."""
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE lit.`identifiers.fingerprint` = $fingerprint
                RETURN lit
                """
                
                result = await session.run(query, fingerprint=fingerprint)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by fingerprint {fingerprint}: {e}")
            return None
    
    async def update_literature(self, lid: str, updates: Dict[str, Any]) -> bool:
        """
        Update a literature node.
        
        :param lid: Literature ID to update
        :param updates: Dictionary of fields to update
        :return: True if updated successfully
        """
        try:
            async with await self._get_session() as session:
                # Add updated timestamp
                updates["updated_at"] = datetime.now().isoformat()
                
                query = """
                MATCH (lit:Literature {lid: $lid})
                SET lit += $updates
                RETURN lit.lid as lid
                """
                
                result = await session.run(query, lid=lid, updates=updates)
                record = await result.single()
                
                success = record is not None
                if success:
                    logger.info(f"Updated literature {lid}")
                else:
                    logger.warning(f"No literature found with LID {lid} to update")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to update literature {lid}: {e}")
            return False
    
    async def delete_literature(self, lid: str) -> bool:
        """
        Delete a literature node and all its relationships.
        
        :param lid: Literature ID to delete
        :return: True if deleted successfully
        """
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})
                DETACH DELETE lit
                RETURN count(*) as deleted_count
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                success = record and record["deleted_count"] > 0
                if success:
                    logger.info(f"Deleted literature {lid}")
                else:
                    logger.warning(f"No literature found with LID {lid} to delete")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete literature {lid}: {e}")
            return False
    
    async def search_literature(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[LiteratureSummaryDTO]:
        """
        Search literature using fulltext index.
        
        :param query: Search query
        :param limit: Maximum number of results
        :param offset: Offset for pagination
        :return: List of literature summaries
        """
        try:
            async with await self._get_session() as session:
                cypher_query = """
                CALL db.index.fulltext.queryNodes("literature_fulltext", $search_text)
                YIELD node, score
                RETURN node
                ORDER BY score DESC
                SKIP $offset
                LIMIT $limit
                """
                
                result = await session.run(
                    cypher_query,
                    search_text=query,
                    offset=offset,
                    limit=limit
                )
                
                results = []
                async for record in result:
                    literature = self._neo4j_node_to_literature_model(record["node"])
                    if literature:
                        results.append(literature_to_summary_dto(literature))
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to search literature: {e}")
            return []
    
    async def get_literature_count(self) -> int:
        """Get total count of literature nodes."""
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                RETURN count(lit) as count
                """
                
                result = await session.run(query)
                record = await result.single()
                
                return record["count"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to get literature count: {e}")
            return 0
    
    # ========== Graph-specific Operations (Phase 2 Ready) ==========
    
    async def get_out_degree(self, lid: str) -> int:
        """
        Get out-degree (number of citations) for a literature.
        
        :param lid: Literature ID
        :return: Number of outgoing CITES relationships
        """
        try:
            async with await self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})-[:CITES]->()
                RETURN count(*) as out_degree
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                return record["out_degree"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to get out-degree for {lid}: {e}")
            return 0
    
    async def get_in_degree(self, lid: str) -> int:
        """
        Get in-degree (number of times cited) for a literature.
        
        :param lid: Literature ID
        :return: Number of incoming CITES relationships
        """
        try:
            async with await self._get_session() as session:
                query = """
                MATCH ()-[:CITES]->(lit:Literature {lid: $lid})
                RETURN count(*) as in_degree
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                return record["in_degree"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to get in-degree for {lid}: {e}")
            return 0
    
    # ========== Helper Methods ==========
    
    def _neo4j_node_to_literature_model(self, node) -> Optional[LiteratureModel]:
        """Convert Neo4j node to LiteratureModel."""
        try:
            # 从Neo4j节点属性重构LiteratureModel
            from ..models.literature import (
                IdentifiersModel,
                MetadataModel,
                ContentModel,
                ReferenceModel,
            )
            
            # 基础属性
            data = {
                "lid": node.get("lid"),
                "user_id": node.get("user_id"),
                "created_at": datetime.fromisoformat(node["created_at"]) if node.get("created_at") else datetime.now(),
                "updated_at": datetime.fromisoformat(node["updated_at"]) if node.get("updated_at") else datetime.now(),
                "raw_data": node.get("raw_data", {})
            }
            
            # 结构化数据
            data["identifiers"] = IdentifiersModel(**(node.get("identifiers") or {}))
            data["metadata"] = MetadataModel(**(node.get("metadata") or {}))
            data["content"] = ContentModel(**(node.get("content") or {}))
            
            # 引用数据 (从临时存储恢复)
            temp_refs = node.get("temp_references", [])
            data["references"] = [ReferenceModel(**ref) for ref in temp_refs] if temp_refs else []
            
            return LiteratureModel(**data)
            
        except Exception as e:
            logger.error(f"Failed to convert Neo4j node to LiteratureModel: {e}")
            return None
