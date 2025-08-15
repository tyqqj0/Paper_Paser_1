"""
Neo4j Relationship Data Access Object for managing literature citation relationships.

This module provides Neo4j implementation for literature relationships,
using native graph relationships instead of separate collection documents.
Replaces the original MongoDB implementation with enhanced graph capabilities.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from neo4j import AsyncDriver, AsyncSession

from literature_parser_backend.models.relationship import (
    LiteratureRelationshipModel,
    RelationshipType,
    CitationGraphNode,
)
from .base_dao import BaseNeo4jDAO

logger = logging.getLogger(__name__)


class RelationshipDAO(BaseNeo4jDAO):
    """Neo4j Data Access Object for literature relationship operations."""
    
    # Inherits __init__, create_from_* methods, and _get_session from BaseNeo4jDAO
    
    # ========== Core Relationship Operations ==========
    
    async def create_or_update_relationship(
        self,
        relationship: LiteratureRelationshipModel
    ) -> str:
        """
        Create or update a literature relationship using native Neo4j relationships.
        
        :param relationship: Relationship model to create/update
        :return: Relationship ID (element_id)
        """
        try:
            async with self._get_session() as session:
                # Update timestamps
                relationship.updated_at = datetime.now()
                if not relationship.created_at:
                    relationship.created_at = datetime.now()
                
                query = """
                MATCH (from_lit:Literature {lid: $from_lid})
                MATCH (to_lit:Literature {lid: $to_lid})
                
                MERGE (from_lit)-[rel:CITES]->(to_lit)
                ON CREATE SET
                    rel.relationship_type = $relationship_type,
                    rel.confidence = $confidence,
                    rel.source = $source,
                    rel.created_at = $created_at,
                    rel.metadata = $metadata,
                    rel.verified = $verified
                ON MATCH SET
                    rel.confidence = $confidence,
                    rel.source = $source,
                    rel.updated_at = $updated_at,
                    rel.metadata = $metadata,
                    rel.verified = $verified
                
                RETURN elementId(rel) as relationship_id
                """
                
                result = await session.run(
                    query,
                    from_lid=relationship.from_lid,
                    to_lid=relationship.to_lid,
                    relationship_type=relationship.relationship_type.value,
                    confidence=relationship.confidence,
                    source=relationship.source,
                    created_at=relationship.created_at.isoformat(),
                    updated_at=relationship.updated_at.isoformat(),
                    metadata=relationship.metadata or {},
                    verified=relationship.verified
                )
                record = await result.single()
                
                if record:
                    relationship_id = record["relationship_id"]
                    logger.info(f"Created/updated relationship: {relationship.from_lid} -> {relationship.to_lid}")
                    return relationship_id
                else:
                    raise RuntimeError("Failed to create/update relationship")
                    
        except Exception as e:
            logger.error(f"Failed to create/update relationship: {e}")
            raise
    
    async def get_citations(
        self,
        from_lid: str,
        relationship_type: Optional[RelationshipType] = None,
        min_confidence: float = 0.0
    ) -> List[LiteratureRelationshipModel]:
        """
        Get all literatures that the given literature cites (outgoing relationships).
        
        :param from_lid: LID of the literature citing others
        :param relationship_type: Filter by relationship type
        :param min_confidence: Minimum confidence threshold
        :return: List of citation relationships
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (from_lit:Literature {lid: $from_lid})-[rel:CITES]->(to_lit:Literature)
                WHERE rel.confidence >= $min_confidence
                """
                
                if relationship_type:
                    query += " AND rel.relationship_type = $relationship_type"
                
                query += """
                RETURN rel, to_lit.lid as to_lid
                ORDER BY rel.confidence DESC
                """
                
                params = {
                    "from_lid": from_lid,
                    "min_confidence": min_confidence
                }
                
                if relationship_type:
                    params["relationship_type"] = relationship_type.value
                
                result = await session.run(query, **params)
                
                relationships = []
                async for record in result:
                    rel = record["rel"]
                    relationship = LiteratureRelationshipModel(
                        from_lid=from_lid,
                        to_lid=record["to_lid"],
                        relationship_type=RelationshipType(rel["relationship_type"]),
                        confidence=rel["confidence"],
                        source=rel["source"],
                        created_at=datetime.fromisoformat(rel["created_at"]),
                        updated_at=datetime.fromisoformat(rel.get("updated_at", rel["created_at"])),
                        metadata=rel.get("metadata", {}),
                        verified=rel.get("verified", False)
                    )
                    relationships.append(relationship)
                
                logger.debug(f"Found {len(relationships)} citations for {from_lid}")
                return relationships
                
        except Exception as e:
            logger.error(f"Failed to get citations for {from_lid}: {e}")
            return []
    
    async def get_cited_by(
        self,
        to_lid: str,
        relationship_type: Optional[RelationshipType] = None,
        min_confidence: float = 0.0
    ) -> List[LiteratureRelationshipModel]:
        """
        Get all literatures that cite the given literature (incoming relationships).
        
        :param to_lid: LID of the literature being cited
        :param relationship_type: Filter by relationship type
        :param min_confidence: Minimum confidence threshold
        :return: List of citing relationships
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (from_lit:Literature)-[rel:CITES]->(to_lit:Literature {lid: $to_lid})
                WHERE rel.confidence >= $min_confidence
                """
                
                if relationship_type:
                    query += " AND rel.relationship_type = $relationship_type"
                
                query += """
                RETURN rel, from_lit.lid as from_lid
                ORDER BY rel.confidence DESC
                """
                
                params = {
                    "to_lid": to_lid,
                    "min_confidence": min_confidence
                }
                
                if relationship_type:
                    params["relationship_type"] = relationship_type.value
                
                result = await session.run(query, **params)
                
                relationships = []
                async for record in result:
                    rel = record["rel"]
                    relationship = LiteratureRelationshipModel(
                        from_lid=record["from_lid"],
                        to_lid=to_lid,
                        relationship_type=RelationshipType(rel["relationship_type"]),
                        confidence=rel["confidence"],
                        source=rel["source"],
                        created_at=datetime.fromisoformat(rel["created_at"]),
                        updated_at=datetime.fromisoformat(rel.get("updated_at", rel["created_at"])),
                        metadata=rel.get("metadata", {}),
                        verified=rel.get("verified", False)
                    )
                    relationships.append(relationship)
                
                logger.debug(f"Found {len(relationships)} citations to {to_lid}")
                return relationships
                
        except Exception as e:
            logger.error(f"Failed to get cited_by for {to_lid}: {e}")
            return []
    
    async def get_relationships_between_sets(
        self,
        from_lids: List[str],
        to_lids: List[str],
        relationship_type: Optional[RelationshipType] = None
    ) -> List[LiteratureRelationshipModel]:
        """
        Get all relationships between two sets of literatures.
        
        :param from_lids: List of source literature LIDs
        :param to_lids: List of target literature LIDs
        :param relationship_type: Filter by relationship type
        :return: List of relationships between the sets
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (from_lit:Literature)-[rel:CITES]->(to_lit:Literature)
                WHERE from_lit.lid IN $from_lids AND to_lit.lid IN $to_lids
                """
                
                if relationship_type:
                    query += " AND rel.relationship_type = $relationship_type"
                
                query += """
                RETURN rel, from_lit.lid as from_lid, to_lit.lid as to_lid
                ORDER BY rel.confidence DESC
                """
                
                params = {
                    "from_lids": from_lids,
                    "to_lids": to_lids
                }
                
                if relationship_type:
                    params["relationship_type"] = relationship_type.value
                
                result = await session.run(query, **params)
                
                relationships = []
                async for record in result:
                    rel = record["rel"]
                    relationship = LiteratureRelationshipModel(
                        from_lid=record["from_lid"],
                        to_lid=record["to_lid"],
                        relationship_type=RelationshipType(rel["relationship_type"]),
                        confidence=rel["confidence"],
                        source=rel["source"],
                        created_at=datetime.fromisoformat(rel["created_at"]),
                        updated_at=datetime.fromisoformat(rel.get("updated_at", rel["created_at"])),
                        metadata=rel.get("metadata", {}),
                        verified=rel.get("verified", False)
                    )
                    relationships.append(relationship)
                
                logger.debug(f"Found {len(relationships)} relationships between sets")
                return relationships
                
        except Exception as e:
            logger.error(f"Failed to get relationships between sets: {e}")
            return []
    
    async def delete_relationships_for_literature(self, lid: str) -> int:
        """
        Delete all relationships involving a literature (for cleanup).
        
        :param lid: Literature ID
        :return: Number of relationships deleted
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})-[rel:CITES]-()
                DELETE rel
                RETURN count(*) as deleted_count
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                deleted_count = record["deleted_count"] if record else 0
                logger.info(f"Deleted {deleted_count} relationships for literature {lid}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete relationships for {lid}: {e}")
            return 0
    
    async def get_relationship_stats(self, lid: str) -> Dict[str, int]:
        """
        Get relationship statistics for a literature.
        
        :param lid: Literature ID
        :return: Dictionary with outgoing and incoming relationship counts
        """
        try:
            async with self._get_session() as session:
                # Get outgoing count
                outgoing_query = """
                MATCH (lit:Literature {lid: $lid})-[:CITES]->()
                RETURN count(*) as outgoing_count
                """
                
                result = await session.run(outgoing_query, lid=lid)
                outgoing_record = await result.single()
                outgoing_count = outgoing_record["outgoing_count"] if outgoing_record else 0
                
                # Get incoming count
                incoming_query = """
                MATCH ()-[:CITES]->(lit:Literature {lid: $lid})
                RETURN count(*) as incoming_count
                """
                
                result = await session.run(incoming_query, lid=lid)
                incoming_record = await result.single()
                incoming_count = incoming_record["incoming_count"] if incoming_record else 0
                
                return {
                    "outgoing_count": outgoing_count,
                    "incoming_count": incoming_count,
                    "total_count": outgoing_count + incoming_count
                }
                
        except Exception as e:
            logger.error(f"Failed to get relationship stats for {lid}: {e}")
            return {"outgoing_count": 0, "incoming_count": 0, "total_count": 0}
    
    async def get_citation_graph(
        self,
        center_lids: List[str],
        max_depth: int = 2,
        min_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """
        Get a citation graph centered on given literatures.
        
        :param center_lids: Central literature LIDs
        :param max_depth: Maximum depth to traverse
        :param min_confidence: Minimum confidence threshold
        :return: Graph data with nodes and edges
        """
        try:
            async with self._get_session() as session:
                query = f"""
                MATCH path = (center:Literature)-[:CITES*1..{max_depth}]-(connected:Literature)
                WHERE center.lid IN $center_lids
                AND ALL(rel IN relationships(path) WHERE rel.confidence >= $min_confidence)
                
                UNWIND relationships(path) as rel
                MATCH (from_node)-[rel]->(to_node)
                
                RETURN DISTINCT
                    from_node.lid as from_lid,
                    to_node.lid as to_lid,
                    from_node.metadata.title as from_title,
                    to_node.metadata.title as to_title,
                    rel.confidence as confidence,
                    rel.source as source
                """
                
                result = await session.run(
                    query,
                    center_lids=center_lids,
                    min_confidence=min_confidence
                )
                
                nodes = {}
                edges = []
                
                async for record in result:
                    from_lid = record["from_lid"]
                    to_lid = record["to_lid"]
                    
                    # Add nodes
                    if from_lid not in nodes:
                        nodes[from_lid] = CitationGraphNode(
                            lid=from_lid,
                            title=record["from_title"] or "Unknown Title",
                            is_center=from_lid in center_lids
                        )
                    
                    if to_lid not in nodes:
                        nodes[to_lid] = CitationGraphNode(
                            lid=to_lid,
                            title=record["to_title"] or "Unknown Title",
                            is_center=to_lid in center_lids
                        )
                    
                    # Add edge
                    edges.append({
                        "from_lid": from_lid,
                        "to_lid": to_lid,
                        "confidence": record["confidence"],
                        "source": record["source"]
                    })
                
                return {
                    "nodes": [node.model_dump() for node in nodes.values()],
                    "edges": edges,
                    "center_lids": center_lids,
                    "max_depth": max_depth,
                    "min_confidence": min_confidence
                }
                
        except Exception as e:
            logger.error(f"Failed to get citation graph: {e}")
            return {"nodes": [], "edges": [], "center_lids": center_lids}
    
    # ========== Batch Operations ==========
    
    async def batch_create_relationships(
        self,
        relationships: List[LiteratureRelationshipModel]
    ) -> List[str]:
        """
        Create multiple relationships in a single transaction.
        
        :param relationships: List of relationship models
        :return: List of created relationship IDs
        """
        if not relationships:
            return []
        
        created_ids = []
        
        try:
            async with self._get_session() as session:
                async with session.begin_transaction() as tx:
                    for relationship in relationships:
                        try:
                            # Update timestamps
                            relationship.updated_at = datetime.now()
                            if not relationship.created_at:
                                relationship.created_at = datetime.now()
                            
                            query = """
                            MATCH (from_lit:Literature {lid: $from_lid})
                            MATCH (to_lit:Literature {lid: $to_lid})
                            
                            MERGE (from_lit)-[rel:CITES]->(to_lit)
                            ON CREATE SET
                                rel.relationship_type = $relationship_type,
                                rel.confidence = $confidence,
                                rel.source = $source,
                                rel.created_at = $created_at,
                                rel.metadata = $metadata,
                                rel.verified = $verified
                            
                            RETURN elementId(rel) as relationship_id
                            """
                            
                            result = await tx.run(
                                query,
                                from_lid=relationship.from_lid,
                                to_lid=relationship.to_lid,
                                relationship_type=relationship.relationship_type.value,
                                confidence=relationship.confidence,
                                source=relationship.source,
                                created_at=relationship.created_at.isoformat(),
                                metadata=relationship.metadata or {},
                                verified=relationship.verified
                            )
                            record = await result.single()
                            
                            if record:
                                created_ids.append(record["relationship_id"])
                                
                        except Exception as e:
                            logger.error(f"Failed to create relationship in batch: {e}")
                            # Continue with other relationships
                
                await tx.commit()
                
            logger.info(f"Batch created {len(created_ids)} relationships")
            return created_ids
            
        except Exception as e:
            logger.error(f"Failed to batch create relationships: {e}")
            return []
    
    async def ensure_indexes(self) -> None:
        """Ensure proper indexes exist for relationships."""
        try:
            async with self._get_session() as session:
                # Relationship-specific indexes
                indexes = [
                    "CREATE INDEX cites_confidence_index IF NOT EXISTS FOR ()-[r:CITES]-() ON (r.confidence)",
                    "CREATE INDEX cites_source_index IF NOT EXISTS FOR ()-[r:CITES]-() ON (r.source)",
                    "CREATE INDEX cites_created_index IF NOT EXISTS FOR ()-[r:CITES]-() ON (r.created_at)",
                ]
                
                for index in indexes:
                    try:
                        await session.run(index)
                        logger.info(f"✅ Created relationship index")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            logger.info(f"ℹ️  Relationship index already exists")
                        else:
                            logger.warning(f"⚠️  Failed to create relationship index: {e}")
                
                logger.info("Relationship indexes ensured")
                
        except Exception as e:
            logger.error(f"Failed to ensure relationship indexes: {e}")


    # ========== Citation Relationship Management ==========

    async def create_citation_relationship(
        self,
        citing_lid: str,
        cited_lid: str,
        relationship_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create a :CITES relationship between two literature nodes.
        
        Args:
            citing_lid: LID of the literature that cites
            cited_lid: LID of the literature being cited
            relationship_data: Additional relationship properties
            
        Returns:
            True if relationship created successfully
        """
        try:
            async with self._get_session() as session:
                # Prepare relationship properties
                props = {
                    "created_at": datetime.now().isoformat(),
                    "source": "citation_resolver"
                }
                
                if relationship_data:
                    props.update(relationship_data)
                
                # Create the CITES relationship
                query = """
                MATCH (citing:Literature {lid: $citing_lid})
                MATCH (cited:Literature {lid: $cited_lid})
                MERGE (citing)-[r:CITES]->(cited)
                ON CREATE SET r += $props
                RETURN r.created_at as created_at
                """
                
                result = await session.run(
                    query,
                    citing_lid=citing_lid,
                    cited_lid=cited_lid,
                    props=props
                )
                
                record = await result.single()
                if record:
                    logger.debug(f"✅ Created CITES relationship: {citing_lid} → {cited_lid}")
                    return True
                else:
                    logger.warning(f"❌ Failed to create CITES relationship: {citing_lid} → {cited_lid}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating citation relationship {citing_lid} → {cited_lid}: {e}")
            return False

    async def create_unresolved_citation(
        self,
        citing_lid: str,
        placeholder_lid: str,
        reference_data: Dict[str, Any]
    ) -> bool:
        """
        Create an :Unresolved placeholder node and :CITES relationship.
        
        Args:
            citing_lid: LID of the literature that cites
            placeholder_lid: Generated LID for the placeholder
            reference_data: Raw reference data and metadata
            
        Returns:
            True if placeholder and relationship created successfully
        """
        try:
            async with self._get_session() as session:
                # Prepare node properties (flatten complex objects for Neo4j)
                node_props = {
                    "lid": placeholder_lid,
                    "created_at": datetime.now().isoformat(),
                    "source": "citation_resolver",
                    "status": "unresolved"
                }
                
                # Add parsed reference data (flatten complex structures)
                if "raw_text" in reference_data:
                    node_props["raw_text"] = str(reference_data["raw_text"])
                
                if "parsed_data" in reference_data and reference_data["parsed_data"]:
                    # Flatten parsed_data by converting to JSON string or extracting key fields
                    parsed_data = reference_data["parsed_data"]
                    if isinstance(parsed_data, dict):
                        # Extract common fields as direct properties
                        if "title" in parsed_data:
                            node_props["parsed_title"] = str(parsed_data["title"])
                        if "authors" in parsed_data:
                            node_props["parsed_authors"] = str(parsed_data["authors"]) if parsed_data["authors"] else ""
                        if "year" in parsed_data:
                            node_props["parsed_year"] = str(parsed_data["year"]) if parsed_data["year"] else ""
                        # Store full parsed data as JSON string
                        import json
                        node_props["parsed_data_json"] = json.dumps(parsed_data, ensure_ascii=False)
                
                # No additional cleaning needed - all values are now primitive types
                cleaned_props = node_props
                
                # Create placeholder node and relationship
                query = """
                MATCH (citing:Literature {lid: $citing_lid})
                MERGE (unresolved:Unresolved {lid: $placeholder_lid})
                ON CREATE SET unresolved = $node_props
                MERGE (citing)-[r:CITES]->(unresolved)
                ON CREATE SET r.created_at = $created_at, r.source = 'citation_resolver'
                RETURN unresolved.lid as placeholder_lid, r.created_at as rel_created
                """
                
                result = await session.run(
                    query,
                    citing_lid=citing_lid,
                    placeholder_lid=placeholder_lid,
                    node_props=cleaned_props,
                    created_at=datetime.now().isoformat()
                )
                
                record = await result.single()
                if record:
                    logger.debug(f"✅ Created unresolved placeholder: {citing_lid} → {placeholder_lid}")
                    return True
                else:
                    logger.warning(f"❌ Failed to create unresolved placeholder: {citing_lid} → {placeholder_lid}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating unresolved citation {citing_lid} → {placeholder_lid}: {e}")
            return False

    async def batch_create_unresolved_citations(
        self,
        citing_lid: str,
        unresolved_citations: List[Dict[str, Any]]
    ) -> int:
        """
        Batch create multiple :Unresolved placeholder nodes and :CITES relationships.
        
        改进版本：创建前基于标题标准化进行智能去重，避免同一文献创建多个未解析节点。
        
        Args:
            citing_lid: LID of the literature that cites
            unresolved_citations: List of unresolved citation data
                Each item should have: {
                    "placeholder_lid": str,
                    "reference_data": Dict[str, Any]
                }
            
        Returns:
            Number of successfully created placeholders
        """
        if not unresolved_citations:
            return 0
            
        try:
            async with self._get_session() as session:
                # 🆕 Step 1: 智能去重 - 查找现有的未解析节点进行标题匹配
                from ..utils.title_normalization import normalize_title_for_matching
                
                # 获取现有未解析节点的标题信息
                existing_unresolved = {}  # {normalized_title: existing_lid}
                existing_query = """
                MATCH (u:Unresolved)
                WHERE u.parsed_title IS NOT NULL
                RETURN u.lid as lid, u.parsed_title as title
                """
                
                result = await session.run(existing_query)
                async for record in result:
                    title = record["title"]
                    if title:
                        normalized = normalize_title_for_matching(title)
                        if normalized:
                            existing_unresolved[normalized] = record["lid"]
                
                logger.debug(f"Found {len(existing_unresolved)} existing unresolved nodes for deduplication")
                
                # Step 2: 处理去重和批量数据准备
                deduplicated_citations = {}  # {final_lid: citation_data}
                batch_nodes = []
                batch_relationships = []
                
                # 🆕 批次内去重映射：避免同一批次中的重复
                current_batch_lid_mapping = {}      # {original_lid: final_lid}
                current_batch_title_mapping = {}    # {normalized_title: final_lid}
                
                for citation in unresolved_citations:
                    original_lid = citation["placeholder_lid"]
                    reference_data = citation["reference_data"]
                    
                    # 🆕 Step 2.1: 检查批次内是否已处理过相同的LID
                    if original_lid in current_batch_lid_mapping:
                        final_lid = current_batch_lid_mapping[original_lid]
                        logger.debug(f"📦 Batch LID dedup: {original_lid} → {final_lid}")
                    else:
                        # 🆕 Step 2.2: 检查是否有相同标题（数据库或当前批次）
                        final_lid = original_lid
                        should_create_node = True
                        normalized_title = None
                        
                        # 提取并标准化标题
                        if "parsed_data" in reference_data and reference_data["parsed_data"]:
                            parsed_data = reference_data["parsed_data"]
                            if isinstance(parsed_data, dict) and "title" in parsed_data:
                                title = parsed_data["title"]
                                normalized_title = normalize_title_for_matching(title)
                        
                        if normalized_title:
                            # 优先检查当前批次中的标题重复
                            if normalized_title in current_batch_title_mapping:
                                final_lid = current_batch_title_mapping[normalized_title]
                                should_create_node = False
                                logger.debug(
                                    f"📦 Batch title dedup: {original_lid} → {final_lid} "
                                    f"('{title[:50]}...')"
                                )
                            # 然后检查数据库中的现有节点
                            elif normalized_title in existing_unresolved:
                                final_lid = existing_unresolved[normalized_title]
                                should_create_node = False
                                logger.debug(
                                    f"♻️ Reusing existing unresolved node: "
                                    f"{original_lid} → {final_lid} ('{title[:50]}...')"
                                )
                            else:
                                # 这是新的标题，记录到当前批次映射中
                                current_batch_title_mapping[normalized_title] = original_lid
                        
                        # 记录批次内LID映射
                        current_batch_lid_mapping[original_lid] = final_lid
                        
                        # 记录去重后的引用
                        if final_lid not in deduplicated_citations:
                            deduplicated_citations[final_lid] = {
                                "original_lid": original_lid,
                                "reference_data": reference_data,
                                "should_create_node": should_create_node
                            }
                    
                    # 添加关系数据（每个引用都需要创建关系，即使节点被重用）
                    batch_relationships.append({
                        "citing_lid": citing_lid,
                        "placeholder_lid": final_lid,  # 使用最终确定的LID
                        "created_at": datetime.now().isoformat()
                    })
                
                # Step 3: 准备需要创建的节点数据
                for final_lid, citation_info in deduplicated_citations.items():
                    if not citation_info["should_create_node"]:
                        continue  # 跳过重用的节点
                        
                    reference_data = citation_info["reference_data"]
                    
                    # Prepare node properties (flatten complex objects for Neo4j)
                    node_props = {
                        "lid": final_lid,
                        "created_at": datetime.now().isoformat(),
                        "source": "citation_resolver",
                        "status": "unresolved"
                    }
                    
                    # Add parsed reference data (flatten complex structures)
                    if "raw_text" in reference_data:
                        node_props["raw_text"] = str(reference_data["raw_text"])
                    
                    if "parsed_data" in reference_data and reference_data["parsed_data"]:
                        # Flatten parsed_data by converting to JSON string or extracting key fields
                        parsed_data = reference_data["parsed_data"]
                        if isinstance(parsed_data, dict):
                            # Extract common fields as direct properties
                            if "title" in parsed_data:
                                node_props["parsed_title"] = str(parsed_data["title"])
                            if "authors" in parsed_data:
                                node_props["parsed_authors"] = str(parsed_data["authors"]) if parsed_data["authors"] else ""
                            if "year" in parsed_data:
                                node_props["parsed_year"] = str(parsed_data["year"]) if parsed_data["year"] else ""
                            # Store full parsed data as JSON string
                            import json
                            node_props["parsed_data_json"] = json.dumps(parsed_data, ensure_ascii=False)
                    
                    batch_nodes.append({
                        "lid": final_lid,
                        "props": node_props
                    })
                
                # Step 4: 执行批量创建
                created_count = 0
                
                # 4.1 批量创建新的未解析节点
                if batch_nodes:
                    node_query = """
                    UNWIND $batch_data as item
                    MERGE (unresolved:Unresolved {lid: item.placeholder_lid})
                    ON CREATE SET unresolved = item.node_props
                    RETURN count(unresolved) as created_count
                    """
                    
                    node_batch_data = []
                    for node in batch_nodes:
                        node_batch_data.append({
                            "placeholder_lid": node["lid"],
                            "node_props": node["props"]
                        })
                    
                    result = await session.run(node_query, batch_data=node_batch_data)
                    record = await result.single()
                    node_created = record["created_count"] if record else 0
                    logger.debug(f"Created {node_created} new unresolved nodes")
                
                # 4.2 批量创建引用关系
                if batch_relationships:
                    relationship_query = """
                    MATCH (citing:Literature {lid: $citing_lid})
                    UNWIND $batch_data as item
                    MATCH (unresolved:Unresolved {lid: item.placeholder_lid})
                    MERGE (citing)-[r:CITES]->(unresolved)
                    ON CREATE SET r.created_at = item.created_at, r.source = 'citation_resolver'
                    RETURN count(r) as relationship_count
                    """
                    
                    relationship_batch_data = []
                    for rel in batch_relationships:
                        relationship_batch_data.append({
                            "placeholder_lid": rel["placeholder_lid"],
                            "created_at": rel["created_at"]
                        })
                    
                    result = await session.run(
                        relationship_query,
                        citing_lid=citing_lid,
                        batch_data=relationship_batch_data
                    )
                    
                    record = await result.single()
                    relationship_created = record["relationship_count"] if record else 0
                    logger.debug(f"Created {relationship_created} citation relationships")
                
                # 计算总的创建数量 (去重后的实际节点数)
                total_created = len(deduplicated_citations)
                
                logger.info(
                    f"✅ Smart batch created {total_created} deduplicated unresolved nodes "
                    f"from {len(unresolved_citations)} references for {citing_lid}"
                    f" (deduplication saved {len(unresolved_citations) - total_created} duplicate nodes)"
                )
                
                return total_created
                    
        except Exception as e:
            logger.error(f"Error batch creating unresolved citations for {citing_lid}: {e}")
            return 0

    async def safe_delete_literature(
        self,
        literature_lid: str,
        cascade_delete: bool = True
    ) -> Dict[str, Any]:
        """
        安全删除Literature节点，处理相关的Alias和Unresolved节点。
        
        Args:
            literature_lid: 要删除的Literature LID
            cascade_delete: 是否级联删除相关节点
            
        Returns:
            删除统计信息
        """
        try:
            async with self._get_session() as session:
                stats = {
                    "literature_deleted": 0,
                    "aliases_deleted": 0,
                    "unresolved_deleted": 0,
                    "relationships_deleted": 0
                }
                
                if cascade_delete:
                    # 级联删除策略：删除相关的Alias和孤岛Unresolved节点
                    cascade_query = """
                    MATCH (lit:Literature {lid: $literature_lid})
                    
                    // 收集要删除的相关节点
                    OPTIONAL MATCH (alias:Alias)-[:ALIAS_OF]->(lit)
                    OPTIONAL MATCH (lit)-[:CITES]->(unresolved:Unresolved)
                    WHERE NOT EXISTS((other:Literature)-[:CITES]->(unresolved) WHERE other <> lit)
                    
                    // 删除Literature及其关系，这会自动删除相关关系
                    DETACH DELETE lit
                    
                    // 删除相关的Alias节点（如果有的话）
                    WITH collect(DISTINCT alias) as aliases_to_delete, 
                         collect(DISTINCT unresolved) as unresolved_to_delete
                    
                    UNWIND aliases_to_delete as alias
                    DETACH DELETE alias
                    
                    WITH unresolved_to_delete
                    UNWIND unresolved_to_delete as unresolved
                    DETACH DELETE unresolved
                    
                    RETURN count(DISTINCT aliases_to_delete) as aliases_count,
                           count(DISTINCT unresolved_to_delete) as unresolved_count
                    """
                    
                    result = await session.run(cascade_query, literature_lid=literature_lid)
                    record = await result.single()
                    
                    if record:
                        stats["literature_deleted"] = 1
                        stats["aliases_deleted"] = record.get("aliases_count", 0)
                        stats["unresolved_deleted"] = record.get("unresolved_count", 0)
                        
                        logger.info(
                            f"✅ Safely deleted literature {literature_lid}: "
                            f"{stats['aliases_deleted']} aliases, "
                            f"{stats['unresolved_deleted']} unresolved nodes"
                        )
                else:
                    # 仅删除Literature节点
                    simple_query = """
                    MATCH (lit:Literature {lid: $literature_lid})
                    DETACH DELETE lit
                    RETURN count(lit) as deleted_count
                    """
                    
                    result = await session.run(simple_query, literature_lid=literature_lid)
                    record = await result.single()
                    
                    if record and record["deleted_count"] > 0:
                        stats["literature_deleted"] = 1
                        logger.info(f"✅ Deleted literature {literature_lid} (no cascade)")
                
                return stats
                
        except Exception as e:
            logger.error(f"Error safely deleting literature {literature_lid}: {e}")
            return {"error": str(e)}

    async def upgrade_unresolved_to_literature(
        self,
        placeholder_lid: str,
        literature_lid: str
    ) -> Dict[str, Any]:
        """
        Upgrade an :Unresolved placeholder to point to a real :Literature node.
        
        This is called when a literature matching the placeholder is added to the system.
        
        Args:
            placeholder_lid: LID of the placeholder node
            literature_lid: LID of the real literature node
            
        Returns:
            Dictionary with upgrade statistics
        """
        try:
            async with self._get_session() as session:
                # Find all relationships pointing to the placeholder
                find_query = """
                MATCH (citing:Literature)-[old_rel:CITES]->(placeholder:Unresolved {lid: $placeholder_lid})
                MATCH (literature:Literature {lid: $literature_lid})
                RETURN citing.lid as citing_lid, COUNT(*) as relationship_count
                """
                
                find_result = await session.run(
                    find_query,
                    placeholder_lid=placeholder_lid,
                    literature_lid=literature_lid
                )
                
                citing_lids = []
                total_relationships = 0
                
                async for record in find_result:
                    citing_lids.append(record["citing_lid"])
                    total_relationships += record["relationship_count"]
                
                if not citing_lids:
                    logger.info(f"No relationships found for placeholder {placeholder_lid}")
                    return {"upgraded_relationships": 0, "citing_lids": []}
                
                # Upgrade relationships to point to real literature
                upgrade_query = """
                MATCH (citing:Literature)-[old_rel:CITES]->(placeholder:Unresolved {lid: $placeholder_lid})
                MATCH (literature:Literature {lid: $literature_lid})
                
                // Create new relationship to literature
                MERGE (citing)-[new_rel:CITES]->(literature)
                ON CREATE SET 
                    new_rel.created_at = old_rel.created_at,
                    new_rel.source = old_rel.source,
                    new_rel.confidence = old_rel.confidence,
                    new_rel.upgraded_from = $placeholder_lid,
                    new_rel.upgraded_at = $upgraded_at
                
                // Delete old relationship and placeholder if no other refs
                DELETE old_rel
                
                WITH placeholder, COUNT(old_rel) as deleted_count
                WHERE NOT (()-[:CITES]->(placeholder))
                DELETE placeholder
                
                RETURN deleted_count
                """
                
                upgrade_result = await session.run(
                    upgrade_query,
                    placeholder_lid=placeholder_lid,
                    literature_lid=literature_lid,
                    upgraded_at=datetime.now().isoformat()
                )
                
                upgrade_record = await upgrade_result.single()
                deleted_count = upgrade_record["deleted_count"] if upgrade_record else 0
                
                logger.info(f"✅ Upgraded {len(citing_lids)} relationships from placeholder {placeholder_lid} to literature {literature_lid}")
                
                return {
                    "upgraded_relationships": len(citing_lids),
                    "citing_lids": citing_lids,
                    "deleted_placeholder": deleted_count > 0
                }
                
        except Exception as e:
            logger.error(f"Error upgrading unresolved citation {placeholder_lid} → {literature_lid}: {e}")
            return {"upgraded_relationships": 0, "citing_lids": [], "error": str(e)}

    async def get_unresolved_count(self) -> int:
        """
        Get the total number of unresolved placeholder nodes.
        
        Returns:
            Number of :Unresolved nodes in the database
        """
        try:
            async with self._get_session() as session:
                query = "MATCH (u:Unresolved) RETURN COUNT(u) as count"
                result = await session.run(query)
                record = await result.single()
                return record["count"] if record else 0
                
        except Exception as e:
            logger.error(f"Error getting unresolved count: {e}")
            return 0
