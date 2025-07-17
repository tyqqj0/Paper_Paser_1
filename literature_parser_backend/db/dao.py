"""
Data Access Objects (DAO) for literature management.

This module provides high-level database operations for literature documents,
including creation, retrieval, update, and search functionality.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from ..models.literature import (
    IdentifiersModel,
    LiteratureModel,
    LiteratureSummaryDTO,
    MetadataModel,
    TaskInfoModel,
    literature_to_summary_dto,
)
from ..models.task import ComponentStatus
from .mongodb import literature_collection, get_task_collection

logger = logging.getLogger(__name__)


class LiteratureDAO:
    """Data Access Object for literature collection."""

    def __init__(
        self,
        database: Optional[AsyncIOMotorDatabase[Dict[str, Any]]] = None,
        collection: Optional[AsyncIOMotorCollection[Dict[str, Any]]] = None,
    ) -> None:
        """
        Initialize DAO with database collection.
        
        :param database: Task-level database instance (optional)
        :param collection: Direct collection instance (optional)
        """
        if collection is not None:
            # Use directly provided collection
            self.collection = collection
        elif database is not None:
            # Use task-level database connection
            self.collection = get_task_collection(database)
        else:
            # Fallback to global connection (backward compatibility)
            self.collection = literature_collection()

    @classmethod
    def create_from_global_connection(cls) -> "LiteratureDAO":
        """
        Create DAO instance using global database connection.
        
        This method provides backward compatibility for existing code.
        
        :return: DAO instance using global connection
        """
        return cls()

    @classmethod
    def create_from_task_connection(
        cls, 
        database: AsyncIOMotorDatabase[Dict[str, Any]],
    ) -> "LiteratureDAO":
        """
        Create DAO instance using task-level database connection.
        
        :param database: Task-level database instance
        :return: DAO instance using task connection
        """
        return cls(database=database)

    async def create_literature(self, literature: LiteratureModel) -> str:
        """
        Create a new literature document in the database.

        :param literature: Literature model to create
        :return: ID of the created document
        """
        try:
            # Convert to dict and handle ObjectId
            doc_data = literature.model_dump(by_alias=True, exclude={"id"})

            # Ensure created_at and updated_at are set
            now = datetime.now()
            doc_data["created_at"] = now
            doc_data["updated_at"] = now

            # Insert document
            result = await self.collection.insert_one(doc_data)
            literature_id = str(result.inserted_id)

            logger.info(f"Created literature document with ID: {literature_id}")
            return literature_id

        except Exception as e:
            logger.error(f"Failed to create literature: {e}", exc_info=True)
            raise

    async def get_literature_by_id(
        self,
        literature_id: str,
    ) -> Optional[LiteratureModel]:
        """
        Retrieve a literature document by its ID.

        :param literature_id: ID of the literature document
        :return: Literature model or None if not found
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(literature_id)

            # Find document
            doc = await self.collection.find_one({"_id": object_id})
            if not doc:
                return None

            # Convert to model
            return LiteratureModel(**doc)

        except Exception as e:
            logger.error(f"Failed to get literature by ID {literature_id}: {e}")
            return None

    async def find_by_doi(self, doi: str) -> Optional[LiteratureModel]:
        """
        Find literature by DOI.

        :param doi: DOI to search for
        :return: Literature model or None if not found
        """
        try:
            doc = await self.collection.find_one({"identifiers.doi": doi})
            if not doc:
                return None

            return LiteratureModel(**doc)

        except Exception as e:
            logger.error(f"Failed to find literature by DOI {doi}: {e}")
            return None

    async def find_by_arxiv_id(self, arxiv_id: str) -> Optional[LiteratureModel]:
        """
        Find literature by ArXiv ID.

        :param arxiv_id: ArXiv ID to search for
        :return: Literature model or None if not found
        """
        try:
            doc = await self.collection.find_one({"identifiers.arxiv_id": arxiv_id})
            if not doc:
                return None

            return LiteratureModel(**doc)

        except Exception as e:
            logger.error(f"Failed to find literature by ArXiv ID {arxiv_id}: {e}")
            return None

    async def find_by_fingerprint(self, fingerprint: str) -> Optional[LiteratureModel]:
        """
        Find literature by content fingerprint.

        :param fingerprint: The content-based fingerprint to search for.
        :return: Literature model or None if not found.
        """
        try:
            doc = await self.collection.find_one(
                {"identifiers.fingerprint": fingerprint}
            )
            if not doc:
                return None
            return LiteratureModel(**doc)
        except Exception as e:
            logger.error(f"Failed to find literature by fingerprint {fingerprint}: {e}")
            return None

    async def find_by_task_id(self, task_id: str) -> Optional[LiteratureModel]:
        """
        Find literature by Celery task ID.

        :param task_id: Celery task ID
        :return: Literature model or None if not found
        """
        try:
            doc = await self.collection.find_one({"task_info.task_id": task_id})
            if not doc:
                return None

            return LiteratureModel(**doc)

        except Exception as e:
            logger.error(f"Failed to find literature by task ID {task_id}: {e}")
            return None

    async def search_literature(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[LiteratureSummaryDTO]:
        """Search for literature by title or other fields."""
        # Simple text search for now; can be expanded to use more complex queries
        # or a dedicated search index like Elasticsearch.
        cursor = (
            self.collection.find(
                {"$text": {"$search": query}},
                {
                    "metadata.title": 1,
                    "metadata.authors": 1,
                    "metadata.year": 1,
                    "identifiers.doi": 1,
                    "created_at": 1,
                },
            )
            .limit(limit)
            .skip(offset)
        )

        results = []
        async for doc in cursor:
            # Reconstruct a partial LiteratureModel to create the DTO
            partial_literature = LiteratureModel(
                _id=doc["_id"],
                identifiers=doc.get("identifiers", {}),
                metadata=doc.get("metadata", {}),
                content={},  # Empty content for summary
                references=[],  # Empty references for summary
                created_at=doc.get("created_at"),
                updated_at=doc.get("updated_at"),
            )
            results.append(literature_to_summary_dto(partial_literature))
        return results

    async def update_literature(
        self,
        literature_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update a literature document.

        :param literature_id: ID of the literature to update
        :param updates: Dictionary of fields to update
        :return: True if updated successfully, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(literature_id)

            # Add updated_at timestamp
            updates["updated_at"] = datetime.now()

            # Update document
            result = await self.collection.update_one(
                {"_id": object_id},
                {"$set": updates},
            )

            success = result.modified_count > 0
            if success:
                logger.info(f"Updated literature {literature_id}")
            else:
                logger.warning(f"No literature found with ID {literature_id} to update")

            return success

        except Exception as e:
            logger.error(f"Failed to update literature {literature_id}: {e}")
            return False

    async def delete_literature(self, literature_id: str) -> bool:
        """
        Delete a literature document.

        :param literature_id: ID of the literature to delete
        :return: True if deleted successfully, False otherwise
        """
        try:
            # Convert string ID to ObjectId
            object_id = ObjectId(literature_id)

            # Delete document
            result = await self.collection.delete_one({"_id": object_id})

            success = result.deleted_count > 0
            if success:
                logger.info(f"Deleted literature {literature_id}")
            else:
                logger.warning(f"No literature found with ID {literature_id} to delete")

            return success

        except Exception as e:
            logger.error(f"Failed to delete literature {literature_id}: {e}")
            return False

    async def count_total_literature(self) -> int:
        """
        Get total count of literature documents.

        :return: Total count of documents
        """
        try:
            count = await self.collection.count_documents({})
            return count
        except Exception as e:
            logger.error(f"Failed to count literature documents: {e}")
            return 0

    async def get_recent_literature(
        self,
        limit: int = 10,
    ) -> List[LiteratureSummaryDTO]:
        """
        Get most recently created literature documents.

        :param limit: Maximum number of results
        :return: List of recent literature summaries
        """
        return await self.search_literature(
            query=None,
            limit=limit,
            offset=0,
        )

    async def find_by_title(self, title: str) -> Optional[LiteratureModel]:
        """
        Find literature by exact title match (case-insensitive).

        :param title: Title to search for
        :return: Literature model or None if not found
        """
        try:
            # Case-insensitive exact match
            doc = await self.collection.find_one(
                {"metadata.title": {"$regex": f"^{title}$", "$options": "i"}},
            )
            if not doc:
                return None
            return LiteratureModel(**doc)
        except Exception as e:
            logger.error(f"Failed to find literature by title '{title}': {e}")
            return None

    async def find_by_title_fuzzy(
        self,
        title: str,
        similarity_threshold: float = 0.8,
    ) -> Optional[LiteratureModel]:
        """
        Find literature by fuzzy title match using text search score.

        This requires a text index on 'metadata.title'.

        :param title: Title to search for
        :param similarity_threshold: Minimum similarity score (0.0 to 1.0)
        :return: Literature model or None if not found
        """
        try:
            # Use text search and sort by score
            cursor = self.collection.find(
                {"$text": {"$search": title}},
                {"score": {"$meta": "textScore"}},
            ).sort([("score", {"$meta": "textScore"})])

            # Get the best match
            best_match = await cursor.next() if cursor.fetch_next else None

            if not best_match:
                return None

            # Normalize scores or use another similarity metric if needed
            # For simplicity, we just check if the score is above a threshold.
            # MongoDB's textScore is not normalized, so this is a rough measure.
            if best_match["score"] > similarity_threshold:
                return LiteratureModel(**best_match)

            return None
        except Exception as e:
            logger.error(f"Fuzzy title search failed for '{title}': {e}")
            return None

    async def create_placeholder(self, task_id: str, identifiers: IdentifiersModel) -> str:
        """Create a placeholder literature document to reserve an ID and track status."""
        placeholder = LiteratureModel(
            identifiers=identifiers,
            metadata=MetadataModel(title="Processing..."),
            task_info=TaskInfoModel(task_id=task_id, status="processing"),
        )
        doc = placeholder.model_dump(by_alias=True, exclude={"id"})
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def update_component_status(
        self, literature_id: str, component: str, status: str, message: Optional[str] = None
    ) -> None:
        """Update the status of a specific component for a literature document."""
        update_fields = {
            f"task_info.component_status.{component}": status,
            "updated_at": datetime.now(),
        }
        if message:
            update_fields["task_info.error_message"] = message

        await self.collection.update_one(
            {"_id": ObjectId(literature_id)}, {"$set": update_fields}
        )

    async def finalize_literature(
        self, literature_id: str, final_model: LiteratureModel
    ) -> None:
        """Update the placeholder with the final, fully processed literature data."""
        final_doc = final_model.model_dump(by_alias=True, exclude={"id"})
        final_doc["updated_at"] = datetime.now()
        final_doc["task_info.status"] = "success"
        final_doc["task_info.completed_at"] = datetime.now()

        await self.collection.replace_one(
            {"_id": ObjectId(literature_id)}, final_doc
        )
