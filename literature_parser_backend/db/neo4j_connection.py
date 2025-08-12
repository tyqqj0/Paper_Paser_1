"""
Neo4j connection and session management.

This module provides Neo4j database connection using neo4j Python driver
and manages database sessions for literature and graph operations.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from ..settings import Settings

logger = logging.getLogger(__name__)

# Global driver instance
_driver: Optional[AsyncDriver] = None


async def connect_to_neo4j(settings: Optional[Settings] = None) -> AsyncDriver:
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
        # Create Neo4j driver
        config = settings.neo4j_connection_config
        _driver = AsyncGraphDatabase.driver(
            config["uri"],
            auth=(config["username"], config["password"]),
            database=config["database"],
            max_connection_lifetime=3600,  # 1小时
            max_connection_pool_size=50,
            connection_acquisition_timeout=30,
            encrypted=False  # 开发环境暂时关闭加密
        )
        
        # Test connection
        async with _driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
        logger.info(f"Successfully connected to Neo4j at {config['uri']}")
        
        # Create basic constraints and indexes
        await create_constraints_and_indexes()
        
        return _driver
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise


async def disconnect_from_neo4j() -> None:
    """Disconnect from Neo4j."""
    global _driver
    
    if _driver is not None:
        try:
            await _driver.close()
            logger.info("Disconnected from Neo4j")
        except Exception as e:
            logger.error(f"Error closing Neo4j driver: {e}")
        finally:
            _driver = None


def get_neo4j_driver() -> AsyncDriver:
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
async def get_neo4j_session(**kwargs) -> AsyncGenerator[AsyncSession, None]:
    """
    Get a Neo4j session context manager.
    
    :param kwargs: Additional session parameters
    :return: Async session context manager
    """
    driver = get_neo4j_driver()
    
    async with driver.session(**kwargs) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Neo4j session error: {e}")
            raise


async def create_constraints_and_indexes() -> None:
    """Create necessary constraints and indexes for optimal performance."""
    try:
        async with get_neo4j_session() as session:
            logger.info("Creating Neo4j constraints and indexes...")
            
            # ========== 约束创建 (自动创建对应索引) ==========
            constraints = [
                # Literature节点唯一性约束
                "CREATE CONSTRAINT literature_lid_unique IF NOT EXISTS FOR (n:Literature) REQUIRE n.lid IS UNIQUE",
                
                # Alias节点复合唯一约束  
                "CREATE CONSTRAINT alias_unique IF NOT EXISTS FOR (n:Alias) REQUIRE (n.alias_type, n.alias_value) IS UNIQUE",
                
                # Author节点唯一性约束 (为后续Phase 2准备)
                "CREATE CONSTRAINT author_unique IF NOT EXISTS FOR (n:Author) REQUIRE n.normalized_name IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.info(f"✅ Created constraint: {constraint.split('FOR')[1].split('REQUIRE')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent constraint" in str(e).lower():
                        logger.info(f"ℹ️  Constraint already exists: {constraint}")
                    else:
                        logger.warning(f"⚠️  Failed to create constraint: {e}")
            
            # ========== 性能索引创建 ==========
            indexes = [
                # Literature查询索引
                "CREATE INDEX literature_doi_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.doi`)",
                "CREATE INDEX literature_arxiv_index IF NOT EXISTS FOR (n:Literature) ON (n.`identifiers.arxiv_id`)",
                "CREATE INDEX literature_title_index IF NOT EXISTS FOR (n:Literature) ON (n.`metadata.title`)",
                "CREATE INDEX literature_year_index IF NOT EXISTS FOR (n:Literature) ON (n.`metadata.year`)",
                "CREATE INDEX literature_created_index IF NOT EXISTS FOR (n:Literature) ON (n.created_at)",
                
                # 全文搜索索引 (需要Neo4j Enterprise或使用FULLTEXT)
                "CREATE FULLTEXT INDEX literature_fulltext IF NOT EXISTS FOR (n:Literature) ON EACH [n.`metadata.title`, n.`metadata.abstract`]",
                
                # Unresolved节点索引 (为Phase 2准备)
                "CREATE INDEX unresolved_status_index IF NOT EXISTS FOR (n:Unresolved) ON (n.resolution_status)",
                
                # 关系索引 (为CITES关系优化)
                "CREATE INDEX cites_confidence_index IF NOT EXISTS FOR ()-[r:CITES]-() ON (r.confidence)"
            ]
            
            for index in indexes:
                try:
                    await session.run(index)
                    logger.info(f"✅ Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "equivalent index" in str(e).lower():
                        logger.info(f"ℹ️  Index already exists: {index}")
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

async def create_task_neo4j_driver(settings: Optional[Settings] = None) -> AsyncDriver:
    """
    Create a dedicated Neo4j driver for a single task.
    
    This creates a fresh driver that is isolated from the global
    driver, preventing conflicts in Celery tasks.
    
    :param settings: Application settings (optional)
    :return: Neo4j driver instance for the task
    """
    if settings is None:
        settings = Settings()
    
    try:
        config = settings.neo4j_connection_config
        driver = AsyncGraphDatabase.driver(
            config["uri"],
            auth=(config["username"], config["password"]),
            database=config["database"],
            max_connection_lifetime=1800,  # 30分钟 (任务级连接较短)
            max_connection_pool_size=10,   # 较小的连接池
            connection_acquisition_timeout=15,
            encrypted=False
        )
        
        # Test connection
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
            
        logger.info(f"Task Neo4j driver created successfully")
        return driver
        
    except Exception as e:
        logger.error(f"Failed to create task Neo4j driver: {e}")
        raise


async def close_task_neo4j_driver(driver: AsyncDriver) -> None:
    """Close a task-specific Neo4j driver."""
    try:
        if driver:
            await driver.close()
            logger.info("Task Neo4j driver closed successfully")
    except Exception as e:
        logger.error(f"Error closing task Neo4j driver: {e}")
