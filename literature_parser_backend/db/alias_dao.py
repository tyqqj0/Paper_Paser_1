"""
Alias Data Access Object (DAO) for managing literature identifier mappings.

This module provides database operations for the alias system that maps
external identifiers to Literature IDs (LIDs).
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from literature_parser_backend.models.alias import (
    AliasModel,
    AliasType,
    extract_aliases_from_source,
    normalize_alias_value,
)
from .mongodb import get_task_collection

logger = logging.getLogger(__name__)


class AliasDAO:
    """Data Access Object for alias collection operations."""
    
    def __init__(
        self,
        database: Optional[AsyncIOMotorDatabase[Dict[str, Any]]] = None,
        collection: Optional[AsyncIOMotorCollection[Dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize DAO with database collection.
        
        Args:
            database: Task-level database instance (optional)
            collection: Direct collection instance (optional)
        """
        if collection is not None:
            self.collection = collection
        elif database is not None:
            # Get aliases collection from task-level database
            self.collection = database.aliases
        else:
            # TODO: Fallback to global connection when available
            from .mongodb import get_database
            global_db = get_database()
            self.collection = global_db.aliases
    
    @classmethod
    def create_from_global_connection(cls) -> "AliasDAO":
        """
        Create DAO instance using global database connection.
        
        Returns:
            AliasDAO: DAO instance using global connection
        """
        return cls()
    
    @classmethod
    def create_from_task_connection(
        cls,
        database: AsyncIOMotorDatabase[Dict[str, Any]],
    ) -> "AliasDAO":
        """
        Create DAO instance using task-level database connection.
        
        Args:
            database: Task-level database instance
            
        Returns:
            AliasDAO: DAO instance using task connection
        """
        return cls(database=database)
    
    async def resolve_to_lid(self, source_data: Dict[str, Any]) -> Optional[str]:
        """
        Resolve source data to a Literature ID through alias lookup.
        
        This is the main method used by the API to check if a literature
        already exists before creating a new task.
        
        Args:
            source_data: Source data from literature creation request
            
        Returns:
            Optional[str]: LID if found, None if no alias matches
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
                    logger.info(
                        f"Alias resolved: {alias_type}={alias_value} -> LID={lid}"
                    )
                    return lid
            
            return None
            
        except Exception as e:
            logger.error(f"Error resolving aliases to LID: {e}", exc_info=True)
            return None
    
    async def _lookup_single_alias(
        self, alias_type: AliasType, alias_value: str
    ) -> Optional[str]:
        """
        Look up a single alias in the database.
        
        Args:
            alias_type: Type of alias
            alias_value: Alias value
            
        Returns:
            Optional[str]: LID if found, None otherwise
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            doc = await self.collection.find_one({
                "alias_type": alias_type.value,
                "alias_value": normalized_value
            })
            
            if doc:
                return doc["lid"]
            
            return None
            
        except Exception as e:
            logger.error(
                f"Error looking up alias {alias_type}={alias_value}: {e}"
            )
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
        Create a single alias mapping.
        
        Args:
            alias_type: Type of alias
            alias_value: Alias value
            lid: Literature ID to map to
            confidence: Confidence level (0.0-1.0)
            metadata: Additional metadata
            
        Returns:
            str: ID of created mapping
            
        Raises:
            Exception: If mapping creation fails
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            # Check if mapping already exists
            existing = await self.collection.find_one({
                "alias_type": alias_type.value,
                "alias_value": normalized_value
            })
            
            if existing:
                if existing["lid"] == lid:
                    # Same mapping already exists, return existing ID
                    logger.debug(
                        f"Alias mapping already exists: {alias_type}={normalized_value} -> {lid}"
                    )
                    return str(existing["_id"])
                else:
                    # Different LID mapped - this shouldn't happen normally
                    logger.warning(
                        f"Conflicting alias mapping: {alias_type}={normalized_value} "
                        f"exists as {existing['lid']}, tried to map to {lid}"
                    )
                    return str(existing["_id"])
            
            # Create new mapping
            alias_doc = AliasModel(
                alias_type=alias_type,
                alias_value=normalized_value,
                lid=lid,
                confidence=confidence,
                metadata=metadata or {}
            )
            
            doc_data = alias_doc.model_dump(by_alias=True, exclude={"id"})
            result = await self.collection.insert_one(doc_data)
            
            logger.info(
                f"Created alias mapping: {alias_type}={normalized_value} -> {lid}"
            )
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(
                f"Failed to create alias mapping {alias_type}={alias_value} -> {lid}: {e}",
                exc_info=True
            )
            raise
    
    async def batch_create_mappings(
        self,
        lid: str,
        mappings: Dict[AliasType, str],
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Create multiple alias mappings for a single LID.
        
        Args:
            lid: Literature ID to map to
            mappings: Dictionary of alias_type -> alias_value
            confidence: Confidence level for all mappings
            metadata: Additional metadata for all mappings
            
        Returns:
            List[str]: List of created mapping IDs
        """
        created_ids = []
        
        for alias_type, alias_value in mappings.items():
            if alias_value:  # Skip empty values
                try:
                    mapping_id = await self.create_mapping(
                        alias_type=alias_type,
                        alias_value=alias_value,
                        lid=lid,
                        confidence=confidence,
                        metadata=metadata
                    )
                    created_ids.append(mapping_id)
                except Exception as e:
                    logger.error(
                        f"Failed to create mapping {alias_type}={alias_value}: {e}"
                    )
                    # Continue with other mappings
        
        logger.info(
            f"Batch created {len(created_ids)} alias mappings for LID {lid}"
        )
        return created_ids
    
    async def find_by_lid(self, lid: str) -> List[AliasModel]:
        """
        Find all alias mappings for a given Literature ID.
        
        Args:
            lid: Literature ID to search for
            
        Returns:
            List[AliasModel]: List of alias mappings
        """
        try:
            cursor = self.collection.find({"lid": lid})
            docs = await cursor.to_list(length=None)
            
            return [AliasModel(**doc) for doc in docs]
            
        except Exception as e:
            logger.error(f"Error finding aliases for LID {lid}: {e}")
            return []
    
    async def get_alias_by_id(self, alias_id: str) -> Optional[AliasModel]:
        """
        Get a specific alias mapping by its ID.
        
        Args:
            alias_id: Alias mapping ID
            
        Returns:
            Optional[AliasModel]: Alias model if found
        """
        try:
            from bson import ObjectId
            doc = await self.collection.find_one({"_id": ObjectId(alias_id)})
            
            if doc:
                return AliasModel(**doc)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting alias by ID {alias_id}: {e}")
            return None
    
    async def delete_mappings_for_lid(self, lid: str) -> int:
        """
        Delete all alias mappings for a given Literature ID.
        
        This is useful when a literature is deleted.
        
        Args:
            lid: Literature ID
            
        Returns:
            int: Number of mappings deleted
        """
        try:
            result = await self.collection.delete_many({"lid": lid})
            
            logger.info(f"Deleted {result.deleted_count} alias mappings for LID {lid}")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting aliases for LID {lid}: {e}")
            return 0
    
    async def delete_mapping(
        self, alias_type: AliasType, alias_value: str
    ) -> bool:
        """
        Delete a specific alias mapping.
        
        Args:
            alias_type: Type of alias
            alias_value: Alias value
            
        Returns:
            bool: True if mapping was deleted, False if not found
        """
        try:
            normalized_value = normalize_alias_value(alias_type, alias_value)
            
            result = await self.collection.delete_one({
                "alias_type": alias_type.value,
                "alias_value": normalized_value
            })
            
            if result.deleted_count > 0:
                logger.info(f"Deleted alias mapping: {alias_type}={normalized_value}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"Error deleting alias mapping {alias_type}={alias_value}: {e}"
            )
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the alias collection.
        
        Returns:
            Dict[str, Any]: Statistics including counts by type
        """
        try:
            total_count = await self.collection.count_documents({})
            
            # Count by alias type
            pipeline = [
                {"$group": {"_id": "$alias_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            type_counts = {}
            async for doc in self.collection.aggregate(pipeline):
                type_counts[doc["_id"]] = doc["count"]
            
            return {
                "total_mappings": total_count,
                "mappings_by_type": type_counts,
                "collection_name": self.collection.name
            }
            
        except Exception as e:
            logger.error(f"Error getting alias statistics: {e}")
            return {
                "total_mappings": 0,
                "mappings_by_type": {},
                "error": str(e)
            }
