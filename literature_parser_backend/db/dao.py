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
from .mongodb import get_task_collection, literature_collection

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
                {"identifiers.fingerprint": fingerprint},
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

    async def create_placeholder(
        self,
        task_id: str,
        identifiers: IdentifiersModel,
    ) -> str:
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
        self,
        literature_id: str,
        component: str,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """Update the status of a specific component for a literature document."""
        update_fields = {
            f"task_info.component_status.{component}": status,
            "updated_at": datetime.now(),
        }
        if message:
            update_fields["task_info.error_message"] = message

        await self.collection.update_one(
            {"_id": ObjectId(literature_id)},
            {"$set": update_fields},
        )

    async def finalize_literature(
        self,
        literature_id: str,
        final_model: LiteratureModel,
    ) -> None:
        """Update the placeholder with the final, fully processed literature data."""
        # Get current document to preserve component_status
        current_doc = await self.collection.find_one({"_id": ObjectId(literature_id)})

        final_doc = final_model.model_dump(by_alias=True, exclude={"id"})
        final_doc["updated_at"] = datetime.now()

        # Calculate overall status based on component statuses instead of always "success"
        if (
            current_doc
            and "task_info" in current_doc
            and "component_status" in current_doc["task_info"]
        ):
            component_status = current_doc["task_info"]["component_status"]
            final_doc["task_info"]["component_status"] = component_status
            # Calculate overall status based on component statuses
            overall_status = await self._calculate_overall_status(component_status)
            final_doc["task_info"]["status"] = overall_status
        else:
            final_doc["task_info"]["status"] = "success"  # Fallback

        final_doc["task_info"]["completed_at"] = datetime.now()

        await self.collection.replace_one({"_id": ObjectId(literature_id)}, final_doc)

    async def _calculate_overall_status(self, component_status) -> str:
        """
        Calculate overall task status based on enhanced component statuses.

        New Logic (stricter failure handling):
        - Critical components: metadata + references (both required)
        - Optional component: content (nice to have)
        - If any critical component is still processing: processing
        - If all critical components are successful: success
        - If any critical component failed: failed (stricter logic)
        - If no critical components failed but some are still pending: partial_success
        """
        # Extract component statuses - handle multiple formats
        if hasattr(component_status, 'metadata'):
            # New LiteratureComponentStatus object format
            metadata_status = component_status.metadata.status
            content_status = component_status.content.status
            references_status = component_status.references.status
        elif isinstance(component_status, dict) and isinstance(component_status.get("metadata"), dict):
            # Enhanced dict format
            metadata_status = component_status.get("metadata", {}).get(
                "status", "pending",
            )
            content_status = component_status.get("content", {}).get(
                "status", "pending",
            )
            references_status = component_status.get("references", {}).get(
                "status", "pending",
            )
        elif isinstance(component_status, dict):
            # Old simple format (backward compatibility)
            metadata_status = component_status.get("metadata", "pending")
            content_status = component_status.get("content", "pending")
            references_status = component_status.get("references", "pending")
        else:
            return "unknown"

        # Check if any critical component is still processing
        critical_statuses = [
            metadata_status,
            references_status,
        ]  # Updated: references is now critical
        if any(status == "processing" for status in critical_statuses):
            return "processing"

        # Count successful and failed critical components
        successful_critical = sum(
            1 for status in critical_statuses if status == "success"
        )
        failed_critical = sum(1 for status in critical_statuses if status == "failed")

        # Decision logic for critical components (stricter failure logic)
        if successful_critical == len(critical_statuses):
            # All critical components succeeded, but check if content failed
            if content_status == "failed":
                return "completed"  # Critical success, content failure is acceptable
            else:
                return "completed"  # Full success
        elif failed_critical > 0:
            # If any critical component failed, the entire task is failed
            return "failed"
        else:
            # Only show partial_success if no critical components failed but some are still pending
            return "processing"  # Still processing

    async def update_component_status_smart(
        self,
        literature_id: str,
        component: str,
        status: str,
        message: Optional[str] = None,
    ) -> str:
        """
        Smart update of component status with automatic overall status calculation.

        Args:
            literature_id: ID of the literature document
            component: Component name ('metadata', 'content', 'references')
            status: New status ('pending', 'processing', 'success', 'failed')
            message: Optional error message

        Returns:
            The calculated overall task status
        """
        # Update component status
        update_fields = {
            f"task_info.component_status.{component}": status,
            "updated_at": datetime.now(),
        }
        if message:
            update_fields["task_info.error_message"] = message

        await self.collection.update_one(
            {"_id": ObjectId(literature_id)},
            {"$set": update_fields},
        )

        # Get updated document to calculate overall status
        updated_doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if (
            updated_doc
            and "task_info" in updated_doc
            and "component_status" in updated_doc["task_info"]
        ):
            component_status = updated_doc["task_info"]["component_status"]
            overall_status = await self._calculate_overall_status(component_status)

            # Update overall status
            await self.collection.update_one(
                {"_id": ObjectId(literature_id)},
                {"$set": {"task_info.status": overall_status}},
            )

            return overall_status

        return "unknown"

    async def sync_task_status(self, literature_id: str) -> str:
        """
        Synchronize task status by recalculating overall status from component statuses.

        Args:
            literature_id: ID of the literature document

        Returns:
            The synchronized overall task status
        """
        doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if not doc:
            logger.error(
                f"Literature document {literature_id} not found for status sync",
            )
            return "unknown"

        if "task_info" not in doc or "component_status" not in doc["task_info"]:
            logger.warning(f"No component status found for literature {literature_id}")
            return "unknown"

        component_status = doc["task_info"]["component_status"]
        overall_status = await self._calculate_overall_status(component_status)

        # Update overall status if different
        current_overall = doc["task_info"].get("status", "unknown")
        if current_overall != overall_status:
            await self.collection.update_one(
                {"_id": ObjectId(literature_id)},
                {
                    "$set": {
                        "task_info.status": overall_status,
                        "updated_at": datetime.now(),
                    },
                },
            )
            logger.info(
                f"Synchronized task status for {literature_id}: {current_overall} -> {overall_status}",
            )

        return overall_status

    async def update_enhanced_component_status(
        self,
        literature_id: str,
        component: str,
        status: str,
        stage: str,
        progress: int = 0,
        error_info: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        next_action: Optional[str] = None,
        dependencies_met: bool = True,
    ) -> str:
        """
        Update enhanced component status with detailed information.

        Args:
            literature_id: ID of the literature document
            component: Component name ('metadata', 'content', 'references')
            status: New status ('pending', 'processing', 'success', 'failed', 'waiting', 'skipped')
            stage: Detailed stage description
            progress: Progress percentage (0-100)
            error_info: Error information if failed
            source: Data source that succeeded
            next_action: Description of next action
            dependencies_met: Whether dependencies are satisfied

        Returns:
            The calculated overall task status
        """
        from datetime import datetime

        now = datetime.now()

        # Prepare update fields for enhanced component status
        update_fields = {
            f"task_info.component_status.{component}.status": status,
            f"task_info.component_status.{component}.stage": stage,
            f"task_info.component_status.{component}.progress": progress,
            f"task_info.component_status.{component}.dependencies_met": dependencies_met,
            "updated_at": now,
        }

        # Update timestamps based on status
        if status == "processing":
            update_fields[f"task_info.component_status.{component}.started_at"] = now
            # Increment attempts
            current_doc = await self.collection.find_one(
                {"_id": ObjectId(literature_id)},
            )
            if current_doc:
                current_attempts = (
                    current_doc.get("task_info", {})
                    .get("component_status", {})
                    .get(component, {})
                    .get("attempts", 0)
                )
                update_fields[f"task_info.component_status.{component}.attempts"] = (
                    current_attempts + 1
                )
        elif status in ["success", "failed", "skipped"]:
            update_fields[f"task_info.component_status.{component}.completed_at"] = now

        # Add optional fields if provided
        if error_info:
            update_fields[f"task_info.component_status.{component}.error_info"] = (
                error_info
            )
        if source:
            update_fields[f"task_info.component_status.{component}.source"] = source
        if next_action:
            update_fields[f"task_info.component_status.{component}.next_action"] = (
                next_action
            )

        # Update the document
        await self.collection.update_one(
            {"_id": ObjectId(literature_id)},
            {"$set": update_fields},
        )

        # Get updated document to calculate overall status
        updated_doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if (
            updated_doc
            and "task_info" in updated_doc
            and "component_status" in updated_doc["task_info"]
        ):
            component_status = updated_doc["task_info"]["component_status"]
            overall_status = await self._calculate_overall_status(component_status)

            # Update overall status
            await self.collection.update_one(
                {"_id": ObjectId(literature_id)},
                {"$set": {"task_info.status": overall_status}},
            )

            return overall_status

        return "unknown"

    async def check_component_dependencies(
        self, literature_id: str, component: str,
    ) -> bool:
        """
        Check if a component's dependencies are satisfied.

        Args:
            literature_id: ID of the literature document
            component: Component name to check dependencies for

        Returns:
            True if dependencies are satisfied, False otherwise
        """
        doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if not doc:
            return False

        component_status = doc.get("task_info", {}).get("component_status", {})

        # Define dependency rules
        if component == "references":
            # References depends on either metadata or content being successful
            metadata_status = component_status.get("metadata", {}).get(
                "status", "pending",
            )
            content_status = component_status.get("content", {}).get(
                "status", "pending",
            )

            # References can proceed if metadata is successful OR content is successful
            return metadata_status == "success" or content_status == "success"

        # Metadata and content have no dependencies
        return True

    async def get_component_next_actions(self, literature_id: str) -> Dict[str, str]:
        """
        Get next actions for all components based on their current status.

        Args:
            literature_id: ID of the literature document

        Returns:
            Dictionary mapping component names to their next actions
        """
        doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if not doc:
            return {}

        component_status = doc.get("task_info", {}).get("component_status", {})
        next_actions = {}

        for component in ["metadata", "content", "references"]:
            comp_status = component_status.get(component, {})
            status = comp_status.get("status", "pending")

            if status == "pending":
                if component == "metadata":
                    next_actions[component] = "准备从外部API获取元数据"
                elif component == "content":
                    next_actions[component] = "准备下载PDF文件"
                elif component == "references":
                    deps_met = await self.check_component_dependencies(
                        literature_id, component,
                    )
                    if deps_met:
                        next_actions[component] = "准备获取参考文献"
                    else:
                        next_actions[component] = "等待元数据或内容获取完成"
            elif status == "processing":
                next_actions[component] = (
                    f"正在处理 - {comp_status.get('stage', '未知阶段')}"
                )
            elif status == "failed":
                attempts = comp_status.get("attempts", 0)
                max_attempts = comp_status.get("max_attempts", 3)
                if attempts < max_attempts:
                    next_actions[component] = f"准备重试 ({attempts}/{max_attempts})"
                else:
                    next_actions[component] = "已达到最大重试次数"

        return next_actions

    async def get_component_status(
        self, literature_id: str,
    ) -> Optional[Dict[str, str]]:
        """
        Get component status for a literature document.

        Args:
            literature_id: ID of the literature document

        Returns:
            Dictionary with component statuses or None if not found
        """
        doc = await self.collection.find_one({"_id": ObjectId(literature_id)})
        if not doc:
            return None

        if "task_info" not in doc or "component_status" not in doc["task_info"]:
            return None

        return doc["task_info"]["component_status"]

    async def get_literature_processing_status(
        self, literature_id: str
    ) -> Optional["LiteratureProcessingStatus"]:
        """获取文献的完整处理状态"""
        from literature_parser_backend.models.task import (
            LiteratureProcessingStatus,
            ComponentDetail,
            ComponentStatus,
        )

        literature = await self.get_literature_by_id(literature_id)
        if not literature or not literature.task_info:
            return None

        # 构建详细状态信息
        def build_component_detail(component_data) -> ComponentDetail:
            """从数据库数据构建ComponentDetail"""
            if hasattr(component_data, 'status'):
                # 新格式 - EnhancedComponentStatus对象
                return ComponentDetail(
                    status=ComponentStatus(component_data.status),
                    stage=component_data.stage,
                    progress=component_data.progress,
                    started_at=component_data.started_at,
                    completed_at=component_data.completed_at,
                    error_info=component_data.error_info,
                    source=component_data.source,
                    attempts=component_data.attempts,
                    max_attempts=component_data.max_attempts
                )
            else:
                # 旧格式 - 简单字符串
                return ComponentDetail(
                    status=ComponentStatus(component_data if isinstance(component_data, str) else "pending"),
                    stage="等待开始",
                    progress=0
                )

        # 获取组件状态
        component_status = literature.task_info.component_status

        if hasattr(component_status, 'metadata'):
            # 新的增强格式 - LiteratureComponentStatus对象
            metadata_detail = build_component_detail(component_status.metadata)
            content_detail = build_component_detail(component_status.content)
            references_detail = build_component_detail(component_status.references)
        elif isinstance(component_status, dict):
            # 旧的简单格式 - 字典
            metadata_detail = build_component_detail(component_status.get("metadata", "pending"))
            content_detail = build_component_detail(component_status.get("content", "pending"))
            references_detail = build_component_detail(component_status.get("references", "pending"))
        else:
            # 未知格式，使用默认值
            metadata_detail = build_component_detail("pending")
            content_detail = build_component_detail("pending")
            references_detail = build_component_detail("pending")

        # 计算整体状态和进度
        overall_status = await self._calculate_overall_status(component_status)
        overall_progress = self._calculate_overall_progress_from_details(
            metadata_detail, content_detail, references_detail
        )

        # 构建组件状态
        from literature_parser_backend.models.task import LiteratureComponentStatus
        component_status = LiteratureComponentStatus(
            metadata=metadata_detail,
            content=content_detail,
            references=references_detail
        )

        return LiteratureProcessingStatus(
            literature_id=literature_id,
            overall_status=overall_status,
            overall_progress=overall_progress,
            component_status=component_status,
            created_at=literature.created_at,
            updated_at=literature.updated_at
        )



    def _calculate_overall_progress_from_details(
        self, metadata: "ComponentDetail", content: "ComponentDetail", references: "ComponentDetail"
    ) -> int:
        """计算整体进度（三个组件的平均值）"""
        total_progress = metadata.progress + content.progress + references.progress
        return total_progress // 3

    async def archive_failed_literature(self, literature_id: str):
        """软删除失败的文献"""
        await self.collection.update_one(
            {"_id": ObjectId(literature_id)},
            {
                "$set": {
                    "task_info.status": "archived",
                    "archived_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            }
        )
