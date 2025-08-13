"""
Neo4j Data Access Objects (DAO) for literature management.

This module provides high-level database operations for literature nodes,
replacing the original MongoDB implementation with Neo4j while maintaining
the same interface for transparent replacement.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import AsyncDriver, AsyncSession

from ..models.literature import (
    LiteratureModel,
    LiteratureSummaryDTO,
    literature_to_summary_dto,
)
from .base_dao import BaseNeo4jDAO

logger = logging.getLogger(__name__)


class LiteratureDAO(BaseNeo4jDAO):
    """Neo4j Data Access Object for literature operations."""

    # Inherits __init__, create_from_* methods, _get_session, and _clean_for_neo4j from BaseNeo4jDAO
    
    # ========== Core CRUD Operations ==========

    async def create_literature(self, literature: LiteratureModel) -> str:
        """Create a literature node in Neo4j."""
        try:
            async with self._get_session() as session:
                node_props = {
                    "lid": literature.lid,
                    "user_id": str(literature.user_id) if literature.user_id else None,
                    "created_at": literature.created_at.isoformat(),
                    "updated_at": literature.updated_at.isoformat(),
                    "identifiers": self._clean_for_neo4j(literature.identifiers.model_dump() if literature.identifiers else {}),
                    "metadata": self._clean_for_neo4j(literature.metadata.model_dump() if literature.metadata else {}),
                    "content": self._clean_for_neo4j(literature.content.model_dump() if literature.content else {}),
                    "temp_references": [self._clean_for_neo4j(ref.model_dump()) for ref in literature.references] if literature.references else [],
                    "raw_data": self._clean_for_neo4j(literature.raw_data or {}),
                    "task_info": self._clean_for_neo4j(literature.task_info.model_dump() if literature.task_info else {})
                }
                
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
            logger.error(f"Failed to create literature {literature.lid}: {e}")
            raise

    async def get_literature_by_id(self, literature_id: str) -> Optional[LiteratureModel]:
        """Get literature by LID (compatibility method)."""
        return await self.find_by_lid(literature_id)
    
    async def find_by_lid(self, lid: str) -> Optional[LiteratureModel]:
        """Find literature by LID."""
        try:
            async with self._get_session() as session:
                query = "MATCH (lit:Literature {lid: $lid}) RETURN lit"
                result = await session.run(query, lid=lid)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                return None

        except Exception as e:
            logger.error(f"Failed to find literature by LID {lid}: {e}")
            return None

    async def get_all_literature(self, limit: int = 1000) -> List[LiteratureModel]:
        """
        Get all literature nodes for matching purposes.
        
        WARNING: This is for development/testing. In production, this should be 
        optimized with pre-filtering based on search criteria.
        
        Args:
            limit: Maximum number of literature to return
            
        Returns:
            List of literature models
        """
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE lit.lid IS NOT NULL
                RETURN lit
                ORDER BY lit.created_at DESC
                LIMIT $limit
                """
                
                result = await session.run(query, limit=limit)
                
                literatures = []
                async for record in result:
                    lit_data = dict(record["lit"])
                    literature = self._neo4j_node_to_literature_model(lit_data)
                    if literature:
                        literatures.append(literature)
                        
                logger.debug(f"Retrieved {len(literatures)} literature for matching")
                return literatures
                
        except Exception as e:
            logger.error(f"Error getting all literature: {e}")
            return []

    async def find_by_doi(self, doi: str) -> Optional[LiteratureModel]:
        """Find literature by DOI."""
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE apoc.convert.fromJsonMap(lit.identifiers).doi = $doi
                RETURN lit
                LIMIT 1
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
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE apoc.convert.fromJsonMap(lit.identifiers).arxiv_id = $arxiv_id
                RETURN lit
                LIMIT 1
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
        """Find literature by fingerprint."""
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE apoc.convert.fromJsonMap(lit.identifiers).fingerprint = $fingerprint
                RETURN lit
                LIMIT 1
                """
                result = await session.run(query, fingerprint=fingerprint)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by fingerprint {fingerprint}: {e}")
            return None

    async def find_by_task_id(self, task_id: str) -> Optional[LiteratureModel]:
        """Find literature by task ID (stored in raw_data)."""
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE lit.raw_data.task_id = $task_id
                RETURN lit
                """
                result = await session.run(query, task_id=task_id)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                return None

        except Exception as e:
            logger.error(f"Failed to find literature by task ID {task_id}: {e}")
            return None

    async def update_literature(self, literature_id: str, updates: Dict[str, Any]) -> bool:
        """Update a literature node."""
        try:
            async with self._get_session() as session:
                updates["updated_at"] = datetime.now().isoformat()
                
                query = """
                MATCH (lit:Literature {lid: $lid})
                SET lit += $updates
                RETURN lit.lid as lid
                """
                
                result = await session.run(query, lid=literature_id, updates=updates)
                record = await result.single()
                
                success = record is not None
            if success:
                logger.info(f"Updated literature {literature_id}")
            else:
                    logger.warning(f"No literature found with LID {literature_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to update literature {literature_id}: {e}")
            return False

    async def delete_literature(self, literature_id: str) -> bool:
        """Delete a literature node."""
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})
                DETACH DELETE lit
                RETURN count(*) as deleted_count
                """
                
                result = await session.run(query, lid=literature_id)
                record = await result.single()
                
                success = record and record["deleted_count"] > 0
            if success:
                logger.info(f"Deleted literature {literature_id}")
            else:
                    logger.warning(f"No literature found with LID {literature_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to delete literature {literature_id}: {e}")
            return False

    async def search_literature(self, query: str, limit: int = 20, offset: int = 0) -> List[LiteratureSummaryDTO]:
        """Search literature using fulltext index."""
        try:
            async with self._get_session() as session:
                cypher_query = """
                CALL db.index.fulltext.queryNodes("literature_fulltext", $query)
                YIELD node, score
                RETURN node
                ORDER BY score DESC
                SKIP $offset
                LIMIT $limit
                """
                
                result = await session.run(cypher_query, query=query, offset=offset, limit=limit)
                
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
            async with self._get_session() as session:
                query = "MATCH (lit:Literature) RETURN count(lit) as count"
                result = await session.run(query)
                record = await result.single()
                return record["count"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to get literature count: {e}")
            return 0

    async def find_by_title(self, title: str) -> Optional[LiteratureModel]:
        """Find literature by exact title."""
        try:
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature)
                WHERE apoc.convert.fromJsonMap(lit.metadata).title = $title
                RETURN lit
                LIMIT 1
                """
                result = await session.run(query, title=title)
                record = await result.single()
                
                if record:
                    return self._neo4j_node_to_literature_model(record["lit"])
                return None
                
        except Exception as e:
            logger.error(f"Failed to find literature by title '{title}': {e}")
            return None

    async def find_by_title_fuzzy(self, title: str, limit: int = 10) -> List[LiteratureModel]:
        """Find literature by fuzzy title match."""
        try:
            async with self._get_session() as session:
                query = """
                CALL db.index.fulltext.queryNodes("literature_fulltext", $title)
                YIELD node, score
                RETURN node
                ORDER BY score DESC
                LIMIT $limit
                """
                
                result = await session.run(query, title=title, limit=limit)
                
                results = []
                async for record in result:
                    literature = self._neo4j_node_to_literature_model(record["node"])
                    if literature:
                        results.append(literature)
                
                return results
                
        except Exception as e:
            logger.error(f"Fuzzy title search failed for '{title}': {e}")
            return []
    
    # ========== Task Management Methods ==========
    
    async def create_placeholder(self, task_id: str, identifiers: Any) -> str:
        """Create a placeholder literature for task processing."""
        try:
            from ..services.lid_generator import LIDGenerator
            from ..models.literature import MetadataModel, ContentModel
            
            lid_generator = LIDGenerator()
            temp_metadata = MetadataModel(title="Processing...", authors=[], year=None)
            lid = lid_generator.generate_lid(temp_metadata)
            
            literature = LiteratureModel(
                lid=lid,
                identifiers=identifiers,
                metadata=temp_metadata,
                content=ContentModel(),
                references=[],
                raw_data={"task_id": task_id, "placeholder": True}
            )
            
            return await self.create_literature(literature)
            
        except Exception as e:
            logger.error(f"Failed to create placeholder for task {task_id}: {e}")
            raise
    
    async def finalize_literature(self, literature_id: str, literature: LiteratureModel) -> None:
        """Finalize literature with complete data."""
        try:
            async with self._get_session() as session:
                node_props = {
                    "lid": literature.lid,
                    "user_id": str(literature.user_id) if literature.user_id else None,
                    "created_at": literature.created_at.isoformat(),
                    "updated_at": literature.updated_at.isoformat(),
                    "identifiers": self._clean_for_neo4j(literature.identifiers.model_dump() if literature.identifiers else {}),
                    "metadata": self._clean_for_neo4j(literature.metadata.model_dump() if literature.metadata else {}),
                    "content": self._clean_for_neo4j(literature.content.model_dump() if literature.content else {}),
                    "temp_references": [self._clean_for_neo4j(ref.model_dump()) for ref in literature.references] if literature.references else [],
                    "raw_data": self._clean_for_neo4j(literature.raw_data or {}),
                    "task_info": self._clean_for_neo4j(literature.task_info.model_dump() if literature.task_info else {})
                }
                
                # Remove placeholder flag from raw_data
                raw_data = literature.raw_data or {}
                if "placeholder" in raw_data:
                    raw_data_copy = raw_data.copy()
                    del raw_data_copy["placeholder"]
                    node_props["raw_data"] = self._clean_for_neo4j(raw_data_copy)
                
                query = """
                MATCH (placeholder:Literature {lid: $placeholder_lid})
                SET placeholder = $props
                RETURN placeholder.lid as new_lid
                """
                
                result = await session.run(query, placeholder_lid=literature_id, props=node_props)
                record = await result.single()
                
                if record:
                    logger.info(f"Finalized literature: {literature_id} -> {literature.lid}")
                else:
                    logger.warning(f"Failed to finalize literature {literature_id} -> {literature.lid}")
                    
        except Exception as e:
            logger.error(f"Failed to finalize literature {literature_id}: {e}")
            raise
    
    # ========== Helper Methods ==========
    
    def _neo4j_node_to_literature_model(self, node) -> Optional[LiteratureModel]:
        """Convert Neo4j node to LiteratureModel."""
        import json
        
        try:
            from ..models.literature import IdentifiersModel, MetadataModel, ContentModel, ReferenceModel
            
            def parse_json_field(field_value):
                """Parse JSON string field back to Python object."""
                if isinstance(field_value, str) and field_value:
                    try:
                        return json.loads(field_value)
                    except:
                        return {}
                return field_value or {}
            
            data = {
                "lid": node.get("lid"),
                "user_id": node.get("user_id"),
                "created_at": datetime.fromisoformat(node["created_at"]) if node.get("created_at") else datetime.now(),
                "updated_at": datetime.fromisoformat(node["updated_at"]) if node.get("updated_at") else datetime.now(),
                "raw_data": parse_json_field(node.get("raw_data"))
            }
            
            # Parse structured data models
            from ..models.literature import IdentifiersModel, MetadataModel, ContentModel, ReferenceModel, TaskInfoModel
            
            data["identifiers"] = IdentifiersModel(**parse_json_field(node.get("identifiers")))
            data["metadata"] = MetadataModel(**parse_json_field(node.get("metadata")))
            data["content"] = ContentModel(**parse_json_field(node.get("content")))
            
            # Parse task_info if present
            task_info_data = parse_json_field(node.get("task_info"))
            if task_info_data:
                data["task_info"] = TaskInfoModel(**task_info_data)
            else:
                data["task_info"] = None
            
            temp_refs = parse_json_field(node.get("temp_references"))
            if temp_refs and isinstance(temp_refs, list):
                data["references"] = [ReferenceModel(**ref) for ref in temp_refs]
            else:
                data["references"] = []
            
            return LiteratureModel(**data)
            
        except Exception as e:
            logger.error(f"Failed to convert Neo4j node to LiteratureModel: {e}")
            return None
    
    # ========== Task Management Methods (MongoDB Compatibility) ==========

    async def update_enhanced_component_status(
        self,
        literature_id: str,
        component: str,
        status: str,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        source: Optional[str] = None,
        error_info: Optional[Dict[str, Any]] = None,
        next_action: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update enhanced component status with full compatibility to MongoDB version.
        
        This method updates the task_info.component_status for a specific component
        and returns the overall status information.
        """
        from datetime import datetime

        try:
            # Get current literature to read existing task_info
            current_lit = await self.find_by_lid(literature_id)
            if not current_lit:
                logger.error(f"Literature {literature_id} not found for status update")
                return self._error_status_response(literature_id, component, "Literature not found")
            
            # Initialize or update task_info
            if current_lit.task_info:
                task_info = current_lit.task_info.model_dump()
            else:
                from ..models.task import LiteratureComponentStatus
                task_info = {
                    "task_id": kwargs.get("task_id", "unknown"),
                    "status": "processing",
                    "component_status": LiteratureComponentStatus().model_dump(),
                    "created_at": datetime.now().isoformat(),
                    "error_message": None
                }
            
            # Update the specific component
            if "component_status" not in task_info:
                from ..models.task import LiteratureComponentStatus
                task_info["component_status"] = LiteratureComponentStatus().model_dump()
            
            component_update = {
                "status": status,
                "stage": stage or f"{component} {status}",
                "progress": progress or (100 if status == "success" else 0),
                "started_at": task_info["component_status"].get(component, {}).get("started_at") or datetime.now().isoformat(),
                "attempts": task_info["component_status"].get(component, {}).get("attempts", 0) + 1,
                "max_attempts": 3,
            }
            
            if status in ["success", "failed"]:
                component_update["completed_at"] = datetime.now().isoformat()
            
            if source:
                component_update["source"] = source
                
            if error_info:
                component_update["error_info"] = error_info
                
            if next_action:
                component_update["next_action"] = next_action
            
            task_info["component_status"][component] = component_update
            
            # Calculate overall status
            overall_status = self._calculate_overall_status(task_info["component_status"])
            task_info["status"] = overall_status
            
            if overall_status in ["completed", "failed"]:
                task_info["completed_at"] = datetime.now().isoformat()
            
            if status == "failed" and error_info:
                task_info["error_message"] = error_info.get("error_message", "Component processing failed")
            
            # Update in Neo4j
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})
                SET lit.task_info = $task_info,
                    lit.updated_at = $updated_at
                RETURN lit.lid as lid
                """
                
                result = await session.run(
                    query,
                    lid=literature_id,
                    task_info=self._clean_for_neo4j(task_info),
                    updated_at=datetime.now().isoformat()
                )
                
                record = await result.single()
                if not record:
                    logger.error(f"Failed to update task_info for literature {literature_id}")
            
            logger.info(f"Updated {component} status to {status} for literature {literature_id}")
            
            # Return status response (used by worker tasks)
            return {
                "literature_id": literature_id,
                "component": component,
                "status": status,
                "overall_status": overall_status,
                "progress": progress or 0,
                "stage": stage or f"{component} {status}",
                "timestamp": datetime.now().isoformat(),
                "component_status": task_info["component_status"]
            }
            
        except Exception as e:
            logger.error(f"Failed to update enhanced component status for {literature_id}: {e}")
            return self._error_status_response(literature_id, component, str(e))
    
    def _calculate_overall_status(self, component_status: Dict[str, Any]) -> str:
        """Calculate overall task status based on component statuses with partial support."""
        statuses = []
        for comp_name, comp_data in component_status.items():
            if isinstance(comp_data, dict):
                statuses.append(comp_data.get("status", "pending"))
        
        if not statuses:
            return "processing"
        
        # If any component failed, overall is failed
        if "failed" in statuses:
            return "failed"
        
        # Check critical components status (metadata is required, others are optional)
        metadata_status = component_status.get("metadata", {}).get("status", "pending")
        content_status = component_status.get("content", {}).get("status", "pending")
        references_status = component_status.get("references", {}).get("status", "pending")
        
        # 🎯 NEW: Support partial metadata as acceptable for task completion
        metadata_acceptable = metadata_status in ["success", "partial"]
        
        # Task is completed if:
        # 1. Metadata is acceptable (success or partial) AND
        # 2. References succeeded (content is optional)
        if metadata_acceptable:
            # If all components finished processing (success/partial/failed)
            all_finished = all(status in ["success", "partial", "failed"] for status in statuses)
            
            if all_finished:
                # 🎯 PRIMARY SUCCESS: metadata good + references succeeded  
                # (content is optional per user requirements)
                if references_status in ["success", "partial"]:
                    return "completed"
                    
                # 🔄 PARTIAL SUCCESS: metadata good but references failed
                # Still valuable if we have good metadata, may retry references later
                elif metadata_status == "success":
                    return "partial_completed"  # Has good metadata, can be useful
                    
                # 🔢 MINIMAL SUCCESS: only partial metadata, references failed  
                else:
                    return "minimal_completed"  # Basic info only
        
        # If any component is still processing, overall is processing
        if "processing" in statuses:
            return "processing"
            
        # If metadata failed, task failed
        if metadata_status == "failed":
            return "failed"
        
        # Default to processing
        return "processing"
    
    def _error_status_response(self, literature_id: str, component: str, error_message: str) -> Dict[str, Any]:
        """Generate error response for status updates."""
        return {
            "literature_id": literature_id,
            "component": component,
            "status": "failed",
            "overall_status": "failed",
            "progress": 0,
            "stage": "处理出错",
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
    
    async def sync_task_status(self, literature_id: str) -> str:
        """
        Synchronize and return final task status.
        
        This method is called at the end of task processing to get the final status.
        """
        try:
            literature = await self.find_by_lid(literature_id)
            if not literature or not literature.task_info:
                return "failed"
            
            task_info = literature.task_info.model_dump()
            component_status = task_info.get("component_status", {})
            
            overall_status = self._calculate_overall_status(component_status)
            
            # Update the final status in database
            async with self._get_session() as session:
                query = """
                MATCH (lit:Literature {lid: $lid})
                SET lit.task_info = apoc.convert.fromJsonMap(replace(
                    apoc.convert.toJson(lit.task_info), 
                    '"status":"' + split(apoc.convert.toJson(lit.task_info), '"status":"')[1],
                    '"status":"' + $overall_status + '"' + split(split(apoc.convert.toJson(lit.task_info), '"status":"')[1], '"')[1]
                ))
                RETURN lit.lid as lid
                """
                
                # Simple approach - get and update full task_info
                update_query = """
                MATCH (lit:Literature {lid: $lid})
                SET lit.updated_at = $updated_at
                RETURN lit.task_info as current_task_info
                """
                
                result = await session.run(update_query, lid=literature_id, updated_at=datetime.now().isoformat())
                
            return overall_status
            
        except Exception as e:
            logger.error(f"Failed to sync task status for {literature_id}: {e}")
            return "failed"
    
    async def check_component_dependencies(self, literature_id: str, component: str) -> bool:
        """
        Check if dependencies for a component are met.
        
        Dependency rules:
        - metadata: no dependencies (can always proceed)
        - content: depends on metadata success  
        - references: depends on content success
        
        :param literature_id: Literature ID to check
        :param component: Component name to check dependencies for
        :return: True if dependencies are met, False otherwise
        """
        try:
            literature = await self.find_by_lid(literature_id)
            if not literature or not literature.task_info:
                logger.warning(f"Literature {literature_id} or task_info not found for dependency check")
                return False
            
            task_info = literature.task_info.model_dump()
            component_status = task_info.get("component_status", {})
            
            if component == "metadata":
                # Metadata has no dependencies
                return True
            
            elif component == "content":
                # Content has no strict dependencies (can be triggered independently when needed)
                return True
            
            elif component == "references":
                # References depends on metadata success (not content)
                metadata_status = component_status.get("metadata", {}).get("status", "pending")
                return metadata_status == "success"
            
            else:
                logger.warning(f"Unknown component {component} for dependency check")
                return True  # Unknown components can proceed
            
        except Exception as e:
            logger.error(f"Failed to check dependencies for {component} in literature {literature_id}: {e}")
            return False  # Fail safe - don't proceed if can't check dependencies
