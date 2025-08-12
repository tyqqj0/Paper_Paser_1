"""
Unified Database Manager for MongoDB to Neo4j migration.

This module provides a unified interface that can work with both MongoDB and Neo4j
during the migration period, supporting different operation modes.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..models.literature import LiteratureModel, LiteratureSummaryDTO
from ..settings import DatabaseMode, Settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Unified database manager supporting MongoDB, Neo4j, or dual mode operation.
    
    This manager abstracts database operations and routes them to the appropriate
    backend based on the configured database mode.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize database manager with settings.
        
        :param settings: Application settings
        """
        self.settings = settings or Settings()
        self.mode = self.settings.db_mode
        
        # Initialize DAOs based on mode
        self._mongodb_dao = None
        self._neo4j_dao = None
        self._mongodb_alias_dao = None 
        self._neo4j_alias_dao = None
        
        logger.info(f"DatabaseManager initialized in mode: {self.mode}")
    
    async def initialize(self):
        """Initialize database connections and DAOs based on mode."""
        if self.mode in [DatabaseMode.MONGODB_ONLY, DatabaseMode.DUAL]:
            await self._initialize_mongodb()
        
        if self.mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
            await self._initialize_neo4j()
    
    async def _initialize_mongodb(self):
        """Initialize MongoDB connections and DAOs."""
        try:
            from .dao import LiteratureDAO
            from .alias_dao import AliasDAO
            from .mongodb import connect_to_mongodb
            
            # Ensure MongoDB connection
            await connect_to_mongodb(self.settings)
            
            # Initialize DAOs
            self._mongodb_dao = LiteratureDAO()
            self._mongodb_alias_dao = AliasDAO.create_from_global_connection()
            
            logger.info("MongoDB DAOs initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {e}")
            if self.mode == DatabaseMode.MONGODB_ONLY:
                raise
    
    async def _initialize_neo4j(self):
        """Initialize Neo4j connections and DAOs."""
        try:
            from .neo4j_dao import Neo4jLiteratureDAO
            from .neo4j_alias_dao import Neo4jAliasDAO
            from .neo4j_connection import connect_to_neo4j
            
            # Ensure Neo4j connection
            await connect_to_neo4j(self.settings)
            
            # Initialize DAOs
            self._neo4j_dao = Neo4jLiteratureDAO()
            self._neo4j_alias_dao = Neo4jAliasDAO.create_from_global_connection()
            
            logger.info("Neo4j DAOs initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j: {e}")
            if self.mode == DatabaseMode.NEO4J_ONLY:
                raise
    
    # ========== Literature Operations ==========
    
    async def create_literature(self, literature: LiteratureModel) -> str:
        """Create literature in the appropriate database(s)."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.create_literature(literature)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.create_literature(literature)
        
        elif self.mode == DatabaseMode.DUAL:
            # In dual mode, write to both databases
            results = []
            
            # Try MongoDB first
            try:
                mongo_result = await self._mongodb_dao.create_literature(literature)
                results.append(("mongodb", mongo_result))
            except Exception as e:
                logger.error(f"Failed to create literature in MongoDB: {e}")
            
            # Then Neo4j
            try:
                neo4j_result = await self._neo4j_dao.create_literature(literature)
                results.append(("neo4j", neo4j_result))
            except Exception as e:
                logger.error(f"Failed to create literature in Neo4j: {e}")
            
            if not results:
                raise RuntimeError("Failed to create literature in any database")
            
            # Return the first successful result (prefer Neo4j if both succeed)
            return results[-1][1]
    
    async def find_by_lid(self, lid: str) -> Optional[LiteratureModel]:
        """Find literature by LID from the primary database."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.find_by_lid(lid)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.find_by_lid(lid)
        
        elif self.mode == DatabaseMode.DUAL:
            # In dual mode, prefer Neo4j for reads, fallback to MongoDB
            result = await self._neo4j_dao.find_by_lid(lid)
            if result is None:
                result = await self._mongodb_dao.find_by_lid(lid)
            return result
    
    async def find_by_doi(self, doi: str) -> Optional[LiteratureModel]:
        """Find literature by DOI."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.find_by_doi(doi)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.find_by_doi(doi)
        
        elif self.mode == DatabaseMode.DUAL:
            result = await self._neo4j_dao.find_by_doi(doi)
            if result is None:
                result = await self._mongodb_dao.find_by_doi(doi)
            return result
    
    async def find_by_arxiv_id(self, arxiv_id: str) -> Optional[LiteratureModel]:
        """Find literature by ArXiv ID."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.find_by_arxiv_id(arxiv_id)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.find_by_arxiv_id(arxiv_id)
        
        elif self.mode == DatabaseMode.DUAL:
            result = await self._neo4j_dao.find_by_arxiv_id(arxiv_id)
            if result is None:
                result = await self._mongodb_dao.find_by_arxiv_id(arxiv_id)
            return result
    
    async def find_by_fingerprint(self, fingerprint: str) -> Optional[LiteratureModel]:
        """Find literature by content fingerprint."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.find_by_fingerprint(fingerprint)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.find_by_fingerprint(fingerprint)
        
        elif self.mode == DatabaseMode.DUAL:
            result = await self._neo4j_dao.find_by_fingerprint(fingerprint)
            if result is None:
                result = await self._mongodb_dao.find_by_fingerprint(fingerprint)
            return result
    
    async def update_literature(self, lid: str, updates: Dict[str, Any]) -> bool:
        """Update literature in the appropriate database(s)."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.update_literature(lid, updates)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.update_literature(lid, updates)
        
        elif self.mode == DatabaseMode.DUAL:
            # Update both databases
            mongo_success = False
            neo4j_success = False
            
            try:
                mongo_success = await self._mongodb_dao.update_literature(lid, updates)
            except Exception as e:
                logger.error(f"Failed to update literature in MongoDB: {e}")
            
            try:
                neo4j_success = await self._neo4j_dao.update_literature(lid, updates)
            except Exception as e:
                logger.error(f"Failed to update literature in Neo4j: {e}")
            
            return mongo_success or neo4j_success
    
    async def delete_literature(self, lid: str) -> bool:
        """Delete literature from the appropriate database(s)."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.delete_literature(lid)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.delete_literature(lid)
        
        elif self.mode == DatabaseMode.DUAL:
            # Delete from both databases
            mongo_success = False
            neo4j_success = False
            
            try:
                mongo_success = await self._mongodb_dao.delete_literature(lid)
            except Exception as e:
                logger.error(f"Failed to delete literature from MongoDB: {e}")
            
            try:
                neo4j_success = await self._neo4j_dao.delete_literature(lid)
            except Exception as e:
                logger.error(f"Failed to delete literature from Neo4j: {e}")
            
            return mongo_success or neo4j_success
    
    async def search_literature(
        self, 
        query: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[LiteratureSummaryDTO]:
        """Search literature."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_dao.search_literature(query, limit, offset)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_dao.search_literature(query, limit, offset)
        
        elif self.mode == DatabaseMode.DUAL:
            # Prefer Neo4j for search, fallback to MongoDB
            try:
                return await self._neo4j_dao.search_literature(query, limit, offset)
            except Exception as e:
                logger.warning(f"Neo4j search failed, falling back to MongoDB: {e}")
                return await self._mongodb_dao.search_literature(query, limit, offset)
    
    # ========== Alias Operations ==========
    
    async def resolve_to_lid(self, source_data: Dict[str, Any]) -> Optional[str]:
        """Resolve source data to LID through alias lookup."""
        if self.mode == DatabaseMode.MONGODB_ONLY:
            return await self._mongodb_alias_dao.resolve_to_lid(source_data)
        
        elif self.mode == DatabaseMode.NEO4J_ONLY:
            return await self._neo4j_alias_dao.resolve_to_lid(source_data)
        
        elif self.mode == DatabaseMode.DUAL:
            # Check both databases, prefer Neo4j
            result = await self._neo4j_alias_dao.resolve_to_lid(source_data)
            if result is None:
                result = await self._mongodb_alias_dao.resolve_to_lid(source_data)
            return result
    
    # ========== Neo4j-specific Graph Operations (Phase 2 Ready) ==========
    
    async def get_out_degree(self, lid: str) -> int:
        """Get out-degree (citations count). Only available with Neo4j."""
        if self.mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
            return await self._neo4j_dao.get_out_degree(lid)
        else:
            logger.warning("Graph operations not available in MongoDB-only mode")
            return 0
    
    async def get_in_degree(self, lid: str) -> int:
        """Get in-degree (cited by count). Only available with Neo4j."""
        if self.mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL]:
            return await self._neo4j_dao.get_in_degree(lid)
        else:
            logger.warning("Graph operations not available in MongoDB-only mode")
            return 0
    
    # ========== Factory Methods for Task-level Operations ==========
    
    @classmethod
    def create_for_task(
        cls, 
        mongodb_driver=None, 
        neo4j_driver=None, 
        settings: Optional[Settings] = None
    ) -> "DatabaseManager":
        """
        Create a database manager instance for task-level operations.
        
        :param mongodb_driver: MongoDB database instance for task
        :param neo4j_driver: Neo4j driver instance for task
        :param settings: Application settings
        :return: DatabaseManager instance configured for task operations
        """
        manager = cls(settings)
        
        # Initialize task-level DAOs
        if manager.mode in [DatabaseMode.MONGODB_ONLY, DatabaseMode.DUAL] and mongodb_driver:
            from .dao import LiteratureDAO
            from .alias_dao import AliasDAO
            
            manager._mongodb_dao = LiteratureDAO.create_from_task_connection(mongodb_driver)
            manager._mongodb_alias_dao = AliasDAO.create_from_task_connection(mongodb_driver)
        
        if manager.mode in [DatabaseMode.NEO4J_ONLY, DatabaseMode.DUAL] and neo4j_driver:
            from .neo4j_dao import Neo4jLiteratureDAO
            from .neo4j_alias_dao import Neo4jAliasDAO
            
            manager._neo4j_dao = Neo4jLiteratureDAO.create_from_task_driver(neo4j_driver)
            manager._neo4j_alias_dao = Neo4jAliasDAO.create_from_task_driver(neo4j_driver)
        
        return manager
