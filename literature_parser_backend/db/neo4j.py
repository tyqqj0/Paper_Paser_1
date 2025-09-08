"""
Neo4j connection and session management.

This module provides Neo4j database connection using the neo4j Python driver
and manages literature database operations. It replaces the original mongodb.py
with the same function signatures for transparent replacement.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from ..settings import Settings

logger = logging.getLogger(__name__)

# Global driver instance (replaces MongoDB client)
_driver: Optional[AsyncDriver] = None


async def connect_to_neo4j(
    settings: Optional[Settings] = None,
) -> AsyncDriver:
    """
    Connect to Neo4j and return driver instance.
    
    :param settings: Application settings (optional)
    :return: Neo4j driver instance
    """
    global _driver
    
    if _driver is not None:
        return _driver
    
    if settings is None:
        settings = Settings()
    
    try:
        # 🔧 修复：禁用Neo4j驱动程序的详细日志
        import logging
        neo4j_logger = logging.getLogger("neo4j")
        neo4j_logger.setLevel(logging.WARNING)
        
        # Create Neo4j driver
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            database=settings.neo4j_database,
            max_connection_lifetime=3600,  # 1 hour
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
            encrypted=False  # Development environment
        )
        
        # Test connection
        async with _driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
        logger.info(f"Successfully connected to Neo4j at {settings.neo4j_uri}")
        
        # Create constraints and indexes
        await create_indexes()
        
        return _driver
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise


async def disconnect_from_neo4j() -> None:
    """
    Disconnect from Neo4j.
    """
    global _driver
    
    if _driver is not None:
        try:
            await _driver.close()
            logger.info("Disconnected from Neo4j")
        except Exception as e:
            logger.error(f"Error closing Neo4j driver: {e}")
        finally:
            _driver = None


def get_database() -> AsyncDriver:
    """
    Get the global Neo4j driver instance.
    
    :return: Neo4j driver instance
    :raises: RuntimeError if not connected
    """
    global _driver
    
    if _driver is None:
        raise RuntimeError("Neo4j driver not initialized. Call connect_to_neo4j() first.")
    
    return _driver


@asynccontextmanager
async def get_neo4j_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a Neo4j session context manager.
    
    :return: Async session context manager
    """
    driver = get_database()
    
    async with driver.session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Neo4j session error: {e}")
            raise


# Compatibility aliases
literature_collection = get_neo4j_session
connect_to_mongodb = connect_to_neo4j
disconnect_from_mongodb = disconnect_from_neo4j


async def create_indexes() -> None:
    """Create necessary constraints and indexes for optimal performance."""
    try:
        async with get_neo4j_session() as session:
            logger.info("Creating Neo4j constraints and indexes...")
            
            # ========== Constraints (automatically create indexes) ==========
            constraints = [
                # Literature node uniqueness
                "CREATE CONSTRAINT literature_lid_unique IF NOT EXISTS FOR (n:Literature) REQUIRE n.lid IS UNIQUE",
                
                # Alias node composite uniqueness  
                "CREATE CONSTRAINT alias_unique IF NOT EXISTS FOR (n:Alias) REQUIRE (n.alias_type, n.alias_value) IS UNIQUE",
                
                # Author node uniqueness (for future Phase 2)
                "CREATE CONSTRAINT author_unique IF NOT EXISTS FOR (n:Author) REQUIRE n.normalized_name IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.info(f"✅ Created constraint: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent constraint" in str(e).lower():
                        logger.info(f"ℹ️  Constraint already exists")
                    else:
                        logger.warning(f"⚠️  Failed to create constraint: {e}")
            
            # ========== Performance Indexes ==========
            indexes = [
                # Literature query indexes
                "CREATE INDEX literature_doi_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.doi`)",
                "CREATE INDEX literature_arxiv_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.arxiv_id`)",
                "CREATE INDEX literature_fingerprint_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.fingerprint`)",
                "CREATE INDEX literature_title_index IF NOT EXISTS FOR (n:Literature) ON (n.`metadata.title`)",
                "CREATE INDEX literature_year_index IF NOT EXISTS FOR (n:Literature) ON (n.`metadata.year`)",
                "CREATE INDEX literature_created_index IF NOT EXISTS FOR (n:Literature) ON (n.created_at)",
                
                # Full-text search index for metadata JSON string
                "CREATE FULLTEXT INDEX literature_fulltext IF NOT EXISTS FOR (n:Literature) ON EACH [n.metadata]",
                
                # Unresolved node indexes (for Phase 2)
                "CREATE INDEX unresolved_status_index IF NOT EXISTS FOR (n:Unresolved) ON (n.resolution_status)",
                
                # Relationship indexes
                "CREATE INDEX cites_confidence_index IF NOT EXISTS FOR ()-[r:CITES]-() ON (r.confidence)"
            ]
            
            for index in indexes:
                try:
                    await session.run(index)
                    # logger.info(f"✅ Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent index" in str(e).lower():
                        logger.info(f"ℹ️  Index already exists")
                    else:
                        logger.warning(f"⚠️  Failed to create index: {e}")
            
            logger.info("Neo4j constraints and indexes setup completed")
            
    except Exception as e:
        logger.error(f"Failed to create constraints and indexes: {e}")
        # Don't raise - indexes are not critical for basic operation


async def health_check() -> bool:
    """
    Perform a health check on the Neo4j connection.
    
    :return: True if healthy, False otherwise
    """
    try:
        async with get_neo4j_session() as session:
            result = await session.run("RETURN 1 as health_check")
            record = await result.single()
            
            return record["health_check"] == 1
            
    except Exception as e:
        logger.error(f"Neo4j health check failed: {e}")
        return False


# ===============================================
# Task-level connection management for Celery
# ===============================================

async def create_task_connection(
    settings: Optional[Settings] = None,
) -> Tuple[AsyncDriver, AsyncDriver]:
    """
    Create a dedicated Neo4j driver for a single task.
    
    NOTE: Function signature kept compatible with MongoDB version,
    but returns (driver, driver) instead of (client, database).
    
    :param settings: Application settings (optional)
    :return: Tuple of (driver, driver) for task
    """
    if settings is None:
        settings = Settings()
    
    try:
        # 🔧 修复：禁用任务级Neo4j驱动程序的详细日志
        import logging
        neo4j_logger = logging.getLogger("neo4j")
        neo4j_logger.setLevel(logging.WARNING)
        
        # Create task-specific Neo4j driver
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            database=settings.neo4j_database,
            max_connection_lifetime=1800,  # 30 minutes for tasks
            max_connection_pool_size=10,   # Smaller pool for tasks
            connection_acquisition_timeout=15,
            encrypted=False
        )
        
        # Test connection
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
        logger.info("Task Neo4j driver created successfully")
        
        # Return driver twice to match MongoDB (client, database) signature
        return driver, driver
        
    except Exception as e:
        logger.error(f"Failed to create task Neo4j driver: {e}")
        raise


async def close_task_connection(driver: AsyncDriver) -> None:
    """Close a task-specific Neo4j driver."""
    try:
        if driver:
            await driver.close()
            logger.info("Task Neo4j driver closed successfully")
    except Exception as e:
        logger.error(f"Error closing task Neo4j driver: {e}")


def get_task_collection(database: AsyncDriver) -> AsyncDriver:
    """
    Get task collection equivalent (returns the driver itself).
    
    NOTE: Function kept for compatibility with MongoDB interface.
    In Neo4j context, we just return the driver.
    
    :param database: Neo4j driver (treated as database equivalent)
    :return: Same driver (treated as collection equivalent)
    """
    return database


async def create_task_indexes(database: AsyncDriver) -> None:
    """
    Create essential indexes for task-level operations.
    
    :param database: Neo4j driver instance
    """
    try:
        async with database.session() as session:
            # Essential indexes for task operations
            essential_indexes = [
                "CREATE INDEX literature_doi_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.doi`)",
                "CREATE INDEX literature_arxiv_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.arxiv_id`)",
                "CREATE INDEX literature_fingerprint_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.fingerprint`)",
            ]
            
            for index in essential_indexes:
                try:
                    await session.run(index)
                except Exception:
                    pass  # Index might already exist
            
            logger.info("Essential indexes created for task")
            
    except Exception as e:
        logger.error(f"Failed to create task indexes: {e}")
        # Don't raise - indexes are not critical for task execution
