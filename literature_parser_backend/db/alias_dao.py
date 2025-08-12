"""
Neo4j Alias Data Access Object for managing literature identifier mappings.

This module provides Neo4j implementation of the alias system,
using nodes and relationships to map external identifiers to Literature IDs (LIDs).
Replaces the original MongoDB implementation with the same interface.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import AsyncDriver, AsyncSession

from literature_parser_backend.models.alias import (
    AliasModel,
    AliasType,
    extract_aliases_from_source,
    normalize_alias_value,
)
from .base_dao import BaseNeo4jDAO

logger = logging.getLogger(__name__)


class AliasDAO(BaseNeo4jDAO):
    """Neo4j Data Access Object for alias operations."""
    
    # Inherits __init__ from BaseNeo4jDAO
    
    # Inherits create_from_* methods and _get_session from BaseNeo4jDAO
    
    async def resolve_to_lid(self, source_data: Dict[str, Any]) -> Optional[str]:
        """
        Resolve source data to a Literature ID through alias lookup.
        
        This is the main method used by the API to check if a literature
        already exists before creating a new task.
        
        :param source_data: Source data from literature creation request
        :return: LID if found, None if no alias matches
        """
        try:
            # Extract all possible aliases from source data
            aliases = extract_aliases_from_source(source_data)
            
            if not aliases:
                return None
            
            # Try to resolve any of the aliases to a LID
            for alias_type, alias_value in aliases.items():
                lid = await self._lookup_single_alias(alias_type, alias_value)
                if lid:
                    logger.info(f"Alias resolved: {alias_type}={alias_value} -> LID={lid}")
                    return lid
            
            return None
            
        except Exception as e:
            logger.error(f"Error resolving aliases to LID: {e}", exc_info=True)
            return None
    
    async def _lookup_single_alias(
        self, alias_type: AliasType, alias_value: str
    ) -> Optional[str]:
        """
        Look up a single alias in the Neo4j database.
        
        :param alias_type: Type of alias
        :param alias_value: Alias value
        :return: LID if found, None otherwise
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            async with self._get_session() as session:
                query = """
                MATCH (alias:Alias {alias_type: $alias_type, alias_value: $alias_value})
                -[:IDENTIFIES]->(lit:Literature)
                RETURN lit.lid as lid
                """
                
                result = await session.run(
                    query,
                    alias_type=alias_type.value,
                    alias_value=normalized_value
                )
                record = await result.single()
                
                if record:
                    return record["lid"]
                
                return None
                
        except Exception as e:
            logger.error(f"Error looking up alias {alias_type}={alias_value}: {e}")
            return None
    
    async def create_mapping(
        self,
        alias_type: AliasType,
        alias_value: str,
        lid: str,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a single alias mapping using Neo4j nodes and relationships.
        
        :param alias_type: Type of alias
        :param alias_value: Alias value
        :param lid: Literature ID to map to
        :param confidence: Confidence level (0.0-1.0)
        :param metadata: Additional metadata
        :return: ID of created alias node
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            async with self._get_session() as session:
                # Check if mapping already exists
                existing_query = """
                MATCH (alias:Alias {alias_type: $alias_type, alias_value: $alias_value})
                -[:IDENTIFIES]->(lit:Literature)
                RETURN alias, lit.lid as existing_lid
                """
                
                result = await session.run(
                    existing_query,
                    alias_type=alias_type.value,
                    alias_value=normalized_value
                )
                existing_record = await result.single()
                
                if existing_record:
                    existing_lid = existing_record["existing_lid"]
                    if existing_lid == lid:
                        # Same mapping already exists
                        logger.debug(f"Alias mapping already exists: {alias_type}={normalized_value} -> {lid}")
                        return str(existing_record["alias"].element_id)
                    else:
                        # Different LID mapped - log warning but continue
                        logger.warning(f"Conflicting alias mapping: {alias_type}={normalized_value} "
                                     f"exists as {existing_lid}, tried to map to {lid}")
                        return str(existing_record["alias"].element_id)
                
                # Create new alias node and relationship
                create_query = """
                MATCH (lit:Literature {lid: $lid})
                
                MERGE (alias:Alias {
                    alias_type: $alias_type,
                    alias_value: $alias_value
                })
                ON CREATE SET 
                    alias.confidence = $confidence,
                    alias.created_at = $created_at,
                    alias.metadata = $metadata
                
                MERGE (alias)-[:IDENTIFIES]->(lit)
                
                RETURN alias
                """
                
                result = await session.run(
                    create_query,
                    alias_type=alias_type.value,
                    alias_value=normalized_value,
                    lid=lid,
                    confidence=confidence,
                    created_at=datetime.now().isoformat(),
                    metadata=metadata or {}
                )
                record = await result.single()
                
                if record:
                    alias_id = record["alias"].element_id
                    logger.info(f"Created alias mapping: {alias_type}={normalized_value} -> {lid}")
                    return str(alias_id)
                else:
                    raise RuntimeError("Failed to create alias mapping")
                    
        except Exception as e:
            logger.error(f"Failed to create alias mapping {alias_type}={alias_value} -> {lid}: {e}")
            raise
    
    async def batch_create_mappings(
        self,
        lid: str,
        mappings: Dict[AliasType, str],
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Create multiple alias mappings for a single LID using a single transaction.
        
        :param lid: Literature ID to map to
        :param mappings: Dictionary of alias_type -> alias_value
        :param confidence: Confidence level for all mappings
        :param metadata: Additional metadata for all mappings
        :return: List of created alias node IDs
        """
        created_ids = []
        
        try:
            async with self._get_session() as session:
                # Use a single transaction for all mappings
                tx = await session.begin_transaction()
                try:
                    for alias_type, alias_value in mappings.items():
                        if not alias_value:  # Skip empty values
                            continue
                        
                        try:
                            normalized_value = normalize_alias_value(alias_type, alias_value)
                            
                            query = """
                            MATCH (lit:Literature {lid: $lid})
                            
                            MERGE (alias:Alias {
                                alias_type: $alias_type,
                                alias_value: $alias_value
                            })
                            ON CREATE SET 
                                alias.confidence = $confidence,
                                alias.created_at = $created_at,
                                alias.metadata = $metadata
                            
                            MERGE (alias)-[:IDENTIFIES]->(lit)
                            
                            RETURN alias
                            """
                            
                            result = await tx.run(
                                query,
                                alias_type=alias_type.value,
                                alias_value=normalized_value,
                                lid=lid,
                                confidence=confidence,
                                created_at=datetime.now().isoformat(),
                                metadata=self._clean_for_neo4j(metadata or {})
                            )
                            record = await result.single()
                            
                            if record:
                                created_ids.append(str(record["alias"].element_id))
                                
                        except Exception as e:
                            logger.error(f"Failed to create mapping {alias_type}={alias_value}: {e}")
                            # Continue with other mappings
                
                    await tx.commit()
                    logger.info(f"Batch created {len(created_ids)} alias mappings for LID {lid}")
                    
                except Exception as e:
                    await tx.rollback()
                    logger.error(f"Transaction failed, rolling back: {e}")
                    raise
                finally:
                    await tx.close()
                    
            return created_ids
            
        except Exception as e:
            logger.error(f"Failed to batch create alias mappings: {e}")
            return []
    
    async def find_by_lid(self, lid: str) -> List[AliasModel]:
        """
        Find all alias mappings for a given Literature ID.
        
        :param lid: Literature ID to search for
        :return: List of alias mappings
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (alias:Alias)-[:IDENTIFIES]->(lit:Literature {lid: $lid})
                RETURN alias
                """
                
                result = await session.run(query, lid=lid)
                aliases = []
                
                async for record in result:
                    alias_node = record["alias"]
                    alias_model = AliasModel(
                        alias_type=AliasType(alias_node["alias_type"]),
                        alias_value=alias_node["alias_value"],
                        lid=lid,
                        confidence=alias_node.get("confidence", 1.0),
                        metadata=alias_node.get("metadata", {}),
                        created_at=datetime.fromisoformat(alias_node["created_at"]) if alias_node.get("created_at") else datetime.now()
                    )
                    aliases.append(alias_model)
                
                return aliases
                
        except Exception as e:
            logger.error(f"Error finding aliases for LID {lid}: {e}")
            return []
    
    async def get_alias_by_id(self, alias_id: str) -> Optional[AliasModel]:
        """
        Get a specific alias mapping by its ID.
        
        :param alias_id: Alias mapping ID
        :return: Alias model if found
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (alias:Alias)-[:IDENTIFIES]->(lit:Literature)
                WHERE elementId(alias) = $alias_id
                RETURN alias, lit.lid as lid
                """
                
                result = await session.run(query, alias_id=alias_id)
                record = await result.single()
                
                if record:
                    alias_node = record["alias"]
                    return AliasModel(
                        alias_type=AliasType(alias_node["alias_type"]),
                        alias_value=alias_node["alias_value"],
                        lid=record["lid"],
                        confidence=alias_node.get("confidence", 1.0),
                        metadata=alias_node.get("metadata", {}),
                        created_at=datetime.fromisoformat(alias_node["created_at"]) if alias_node.get("created_at") else datetime.now()
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting alias by ID {alias_id}: {e}")
            return None
    
    async def delete_mappings_for_lid(self, lid: str) -> int:
        """
        Delete all alias mappings for a given Literature ID.
        
        :param lid: Literature ID
        :return: Number of mappings deleted
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (alias:Alias)-[:IDENTIFIES]->(lit:Literature {lid: $lid})
                DETACH DELETE alias
                RETURN count(*) as deleted_count
                """
                
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                deleted_count = record["deleted_count"] if record else 0
                logger.info(f"Deleted {deleted_count} alias mappings for LID {lid}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error deleting aliases for LID {lid}: {e}")
            return 0
    
    async def delete_mapping(self, alias_type: AliasType, alias_value: str) -> bool:
        """
        Delete a specific alias mapping.
        
        :param alias_type: Type of alias
        :param alias_value: Alias value
        :return: True if mapping was deleted, False if not found
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            async with self._get_session() as session:
                query = """
                MATCH (alias:Alias {alias_type: $alias_type, alias_value: $alias_value})
                DETACH DELETE alias
                RETURN count(*) as deleted_count
                """
                
                result = await session.run(
                    query,
                    alias_type=alias_type.value,
                    alias_value=normalized_value
                )
                record = await result.single()
                
                deleted = record and record["deleted_count"] > 0
                if deleted:
                    logger.info(f"Deleted alias mapping: {alias_type}={normalized_value}")
                
                return deleted
                
        except Exception as e:
            logger.error(f"Error deleting alias mapping {alias_type}={alias_value}: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the alias system.
        
        :return: Statistics including counts by type
        """
        try:
            async with self._get_session() as session:
                # Total count
                total_query = "MATCH (alias:Alias) RETURN count(alias) as total_count"
                result = await session.run(total_query)
                total_record = await result.single()
                total_count = total_record["total_count"] if total_record else 0
                
                # Count by type
                type_query = """
                MATCH (alias:Alias)
                RETURN alias.alias_type as alias_type, count(*) as count
                ORDER BY count DESC
                """
                
                result = await session.run(type_query)
                type_counts = {}
                async for record in result:
                    type_counts[record["alias_type"]] = record["count"]
                
                return {
                    "total_mappings": total_count,
                    "mappings_by_type": type_counts,
                    "collection_name": "neo4j_aliases"
                }
                
        except Exception as e:
            logger.error(f"Error getting alias statistics: {e}")
            return {
                "total_mappings": 0,
                "mappings_by_type": {},
                "error": str(e),
                "collection_name": "neo4j_aliases"
            }
