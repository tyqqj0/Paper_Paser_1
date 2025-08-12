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
