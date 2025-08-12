"""
Data Access Object for literature relationships.

This module provides database operations for managing citation relationships
between literatures in the 0.2 system.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from ..models.relationship import (
    LiteratureRelationshipModel, 
    RelationshipType, 
    MatchingSource,
    CitationGraphNode,
    CitationGraphEdge
)
from .mongodb import get_task_connection

logger = logging.getLogger(__name__)


class RelationshipDAO:
    """Data Access Object for literature relationships collection."""

    def __init__(
        self,
        database: Optional[AsyncIOMotorDatabase] = None,
        collection: Optional[AsyncIOMotorCollection] = None,
    ):
        """Initialize DAO with database connection."""
        if collection:
            self.collection = collection
        elif database:
            self.collection = database["literature_relationships"]
        else:
            # Use default connection
            database = get_task_connection()
            self.collection = database["literature_relationships"]

    @classmethod
    def create_from_global_connection(cls):
        """Create DAO using the global database connection."""
        return cls()

    @classmethod
    def create_from_task_connection(cls, database: AsyncIOMotorDatabase):
        """Create DAO using a specific task database connection.""" 
        return cls(database=database)

    async def create_relationship(
        self, 
        relationship: LiteratureRelationshipModel
    ) -> str:
        """
        Create a new literature relationship.
        
        Args:
            relationship: The relationship model to create
            
        Returns:
            The created relationship ID
            
        Raises:
            DuplicateKeyError: If relationship already exists
        """
        try:
            relationship.created_at = datetime.now()
            relationship.updated_at = datetime.now()
            
            relationship_dict = relationship.model_dump()
            
            # Insert with upsert to handle duplicates gracefully
            result = await self.collection.replace_one(
                {
                    "from_lid": relationship.from_lid,
                    "to_lid": relationship.to_lid,
                    "relationship_type": relationship.relationship_type
                },
                relationship_dict,
                upsert=True
            )
            
            relationship_id = str(result.upserted_id) if result.upserted_id else "updated"
            
            logger.info(
                f"Created/updated relationship: {relationship.from_lid} -> {relationship.to_lid}"
            )
            
            return relationship_id
            
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise

    async def get_outgoing_citations(self, lid: str) -> List[LiteratureRelationshipModel]:
        """
        Get all literatures that the given literature cites.
        
        Args:
            lid: Literature ID to query citations for
            
        Returns:
            List of outgoing citation relationships
        """
        try:
            cursor = self.collection.find(
                {"from_lid": lid, "relationship_type": RelationshipType.CITES}
            ).sort("confidence", -1)
            
            relationships = []
            async for doc in cursor:
                relationships.append(LiteratureRelationshipModel(**doc))
                
            logger.info(f"Found {len(relationships)} outgoing citations for {lid}")
            return relationships
            
        except Exception as e:
            logger.error(f"Failed to get outgoing citations for {lid}: {e}")
            return []

    async def get_incoming_citations(self, lid: str) -> List[LiteratureRelationshipModel]:
        """
        Get all literatures that cite the given literature.
        
        Args:
            lid: Literature ID to query citations for
            
        Returns:
            List of incoming citation relationships
        """
        try:
            cursor = self.collection.find(
                {"to_lid": lid, "relationship_type": RelationshipType.CITES}
            ).sort("confidence", -1)
            
            relationships = []
            async for doc in cursor:
                relationships.append(LiteratureRelationshipModel(**doc))
                
            logger.info(f"Found {len(relationships)} incoming citations for {lid}")
            return relationships
            
        except Exception as e:
            logger.error(f"Failed to get incoming citations for {lid}: {e}")
            return []

    async def get_subgraph(self, lids: List[str]) -> Tuple[List[str], List[LiteratureRelationshipModel]]:
        """
        Get the subgraph of relationships within the given set of LIDs.
        
        Args:
            lids: List of Literature IDs to analyze
            
        Returns:
            Tuple of (all_connected_lids, relationships_within_subgraph)
        """
        try:
            # Find all relationships where both from_lid and to_lid are in the given set
            cursor = self.collection.find({
                "$and": [
                    {"from_lid": {"$in": lids}},
                    {"to_lid": {"$in": lids}},
                    {"relationship_type": RelationshipType.CITES}
                ]
            })
            
            relationships = []
            all_lids = set(lids)
            
            async for doc in cursor:
                relationship = LiteratureRelationshipModel(**doc)
                relationships.append(relationship)
                
                # Track all LIDs that appear in relationships
                all_lids.add(relationship.from_lid)
                all_lids.add(relationship.to_lid)
            
            logger.info(
                f"Subgraph analysis: {len(relationships)} relationships "
                f"among {len(all_lids)} literatures"
            )
            
            return list(all_lids), relationships
            
        except Exception as e:
            logger.error(f"Failed to get subgraph: {e}")
            return lids, []

    async def delete_relationships_for_literature(self, lid: str) -> int:
        """
        Delete all relationships involving a literature (for cleanup when literature is deleted).
        
        Args:
            lid: Literature ID to clean up relationships for
            
        Returns:
            Number of relationships deleted
        """
        try:
            # Delete all relationships where this literature is either source or target
            result = await self.collection.delete_many({
                "$or": [
                    {"from_lid": lid},
                    {"to_lid": lid}
                ]
            })
            
            deleted_count = result.deleted_count
            
            logger.info(f"Deleted {deleted_count} relationships for literature {lid}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete relationships for {lid}: {e}")
            return 0

    async def get_relationship_stats(self, lid: str) -> Dict[str, Any]:
        """
        Get citation statistics for a literature.
        
        Args:
            lid: Literature ID to get stats for
            
        Returns:
            Dictionary with citation statistics
        """
        try:
            # Count outgoing citations
            outgoing_count = await self.collection.count_documents({
                "from_lid": lid,
                "relationship_type": RelationshipType.CITES
            })
            
            # Count incoming citations  
            incoming_count = await self.collection.count_documents({
                "to_lid": lid,
                "relationship_type": RelationshipType.CITES
            })
            
            # Get confidence distribution for outgoing citations
            pipeline = [
                {"$match": {"from_lid": lid, "relationship_type": RelationshipType.CITES}},
                {
                    "$group": {
                        "_id": None,
                        "avg_confidence": {"$avg": "$confidence"},
                        "min_confidence": {"$min": "$confidence"},
                        "max_confidence": {"$max": "$confidence"}
                    }
                }
            ]
            
            confidence_stats = {}
            async for doc in self.collection.aggregate(pipeline):
                confidence_stats = {
                    "avg_confidence": doc.get("avg_confidence", 0.0),
                    "min_confidence": doc.get("min_confidence", 0.0),
                    "max_confidence": doc.get("max_confidence", 0.0)
                }
            
            stats = {
                "lid": lid,
                "outgoing_citations": outgoing_count,
                "incoming_citations": incoming_count,
                "total_relationships": outgoing_count + incoming_count,
                **confidence_stats
            }
            
            logger.info(f"Citation stats for {lid}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get relationship stats for {lid}: {e}")
            return {
                "lid": lid,
                "outgoing_citations": 0,
                "incoming_citations": 0,
                "total_relationships": 0
            }

    async def batch_create_relationships(
        self, 
        relationships: List[LiteratureRelationshipModel]
    ) -> List[str]:
        """
        Create multiple relationships in batch.
        
        Args:
            relationships: List of relationship models to create
            
        Returns:
            List of created relationship IDs
        """
        if not relationships:
            return []
            
        try:
            # Prepare bulk operations
            bulk_ops = []
            
            for relationship in relationships:
                relationship.created_at = datetime.now()
                relationship.updated_at = datetime.now()
                
                relationship_dict = relationship.model_dump()
                
                # Use replace_one with upsert for each relationship
                bulk_ops.append({
                    "replaceOne": {
                        "filter": {
                            "from_lid": relationship.from_lid,
                            "to_lid": relationship.to_lid,
                            "relationship_type": relationship.relationship_type
                        },
                        "replacement": relationship_dict,
                        "upsert": True
                    }
                })
            
            if bulk_ops:
                result = await self.collection.bulk_write(bulk_ops, ordered=False)
                
                created_count = result.upserted_count + result.modified_count
                
                logger.info(f"Batch created/updated {created_count} relationships")
                
                return [str(i) for i in range(created_count)]
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to batch create relationships: {e}")
            return []

    async def ensure_indexes(self):
        """Ensure proper indexes exist for the relationships collection."""
        try:
            # Create indexes for efficient querying
            await self.collection.create_index("from_lid")
            await self.collection.create_index("to_lid")
            await self.collection.create_index([("from_lid", 1), ("to_lid", 1)], unique=True)
            await self.collection.create_index("relationship_type")
            await self.collection.create_index("confidence")
            await self.collection.create_index("source")
            await self.collection.create_index("created_at")
            
            logger.info("Relationship collection indexes ensured")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")


