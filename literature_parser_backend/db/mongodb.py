"""
MongoDB connection and collection management.

This module provides MongoDB database connection using Motor
(async MongoDB driver) and manages literature collections.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from ..settings import Settings

logger = logging.getLogger(__name__)

# Global database client and database instances
_client: Optional[AsyncIOMotorClient[Dict[str, Any]]] = None
_database: Optional[AsyncIOMotorDatabase[Dict[str, Any]]] = None


async def connect_to_mongodb(
    settings: Optional[Settings] = None,
) -> AsyncIOMotorDatabase[Dict[str, Any]]:
    """
    Connect to MongoDB and return database instance.

    :param settings: Application settings (optional)
    :return: MongoDB database instance
    """
    global _client, _database

    if _database is not None:
        return _database

    if settings is None:
        settings = Settings()

    try:
        # Create MongoDB client
        _client = AsyncIOMotorClient(
            str(settings.db_url),
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second timeout
            socketTimeoutMS=10000,  # 10 second timeout
        )

        # Get database
        _database = _client.get_database()

        # Test connection by pinging the specific database
        await _database.command("ping")
        logger.info(
            f"Successfully connected to MongoDB at {settings.db_host}:{settings.db_port}, db: {settings.db_base}",
        )

        # Create indexes for better performance
        await create_indexes()

        return _database

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def disconnect_from_mongodb() -> None:
    """Disconnect from MongoDB."""
    global _client, _database

    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("Disconnected from MongoDB")


def get_database() -> AsyncIOMotorDatabase[Dict[str, Any]]:
    """
    Get the current database instance.

    :return: MongoDB database instance
    :raises RuntimeError: If not connected to database
    """
    if _database is None:
        raise RuntimeError(
            "Not connected to database. Call connect_to_mongodb() first.",
        )
    return _database


def literature_collection() -> AsyncIOMotorCollection[Dict[str, Any]]:
    """
    Get the literature collection.

    :return: Literature collection instance
    """
    database = get_database()
    return database.literatures


async def create_indexes() -> None:
    """Create necessary indexes for better query performance."""
    try:
        collection = literature_collection()
        logger.info("Dropping old indexes...")
        try:
            await collection.drop_index("doi_index")
            logger.info("Dropped 'doi_index'.")
        except Exception:
            logger.warning("'doi_index' not found, skipping.")
        try:
            await collection.drop_index("arxiv_id_index")
            logger.info("Dropped 'arxiv_id_index'.")
        except Exception:
            logger.warning("'arxiv_id_index' not found, skipping.")

        logger.info("Creating new smart indexes...")
        
        # 唯一索引：只对非null值生效，避免重复键错误
        await collection.create_index(
            [("identifiers.doi", 1)],
            name="doi_unique_index",
            unique=True,
            partialFilterExpression={"identifiers.doi": {"$type": "string"}},
            background=True,
        )
        await collection.create_index(
            [("identifiers.arxiv_id", 1)],
            name="arxiv_unique_index",
            unique=True,
            partialFilterExpression={"identifiers.arxiv_id": {"$type": "string"}},
            background=True,
        )
        
        # 内容指纹唯一索引
        await collection.create_index(
            [("identifiers.fingerprint", 1)],
            name="fingerprint_unique_index",
            unique=True,
            sparse=True,  # 忽略没有该字段的文档
            background=True,
        )

        # 其他查询索引
        await collection.create_index(
            [("metadata.title", "text"), ("metadata.authors.full_name", "text")],
            name="text_search_index",
            background=True,
        )
        await collection.create_index(
            [("created_at", -1)],
            name="created_at_index",
            background=True,
        )
        await collection.create_index(
            [("task_info.task_id", 1)],
            name="task_id_index",
            background=True,
        )

        logger.info("Successfully created database indexes")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")


async def health_check() -> bool:
    """
    Check if MongoDB connection is healthy.

    :return: True if healthy, False otherwise
    """
    try:
        if _database is None:
            return False

        # Ping the specific database
        await _database.command("ping")
        return True

    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return False


# ===============================================
# Task-level connection management
# ===============================================

async def create_task_connection(
    settings: Optional[Settings] = None,
) -> Tuple[AsyncIOMotorClient[Dict[str, Any]], AsyncIOMotorDatabase[Dict[str, Any]]]:
    """
    Create a dedicated database connection for a single task.
    
    This function creates a fresh connection that is isolated from the global
    connection pool, preventing event loop conflicts in Celery tasks.
    
    :param settings: Application settings (optional)
    :return: Tuple of (client, database) for the task
    """
    if settings is None:
        settings = Settings()

    try:
        # Create new MongoDB client for this task
        client = AsyncIOMotorClient(
            str(settings.db_url),
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second timeout
            socketTimeoutMS=10000,  # 10 second timeout
        )

        # Get database
        database = client.get_database()

        # Test connection by pinging the specific database
        await database.command("ping")
        logger.info(
            f"Task connection established to MongoDB at {settings.db_host}:{settings.db_port}, db: {settings.db_base}",
        )

        return client, database

    except Exception as e:
        logger.error(f"Failed to create task connection to MongoDB: {e}")
        raise


async def close_task_connection(client: AsyncIOMotorClient[Dict[str, Any]]) -> None:
    """
    Close a task-level database connection.
    
    :param client: MongoDB client to close
    """
    try:
        if client:
            client.close()
            logger.info("Task database connection closed")
    except Exception as e:
        logger.error(f"Error closing task database connection: {e}")


def get_task_collection(
    database: AsyncIOMotorDatabase[Dict[str, Any]],
) -> AsyncIOMotorCollection[Dict[str, Any]]:
    """
    Get the literature collection from a task-level database connection.
    
    :param database: Task-level database instance
    :return: Literature collection instance
    """
    return database.literatures


async def create_task_indexes(
    database: AsyncIOMotorDatabase[Dict[str, Any]],
) -> None:
    """
    Create necessary indexes for a task-level database connection.
    
    This is a lightweight version of create_indexes() that only creates
    essential indexes needed for task operations.
    
    :param database: Task-level database instance
    """
    try:
        collection = get_task_collection(database)
        
        # Only create essential indexes for task operations
        logger.info("Creating essential indexes for task...")
        
        # 唯一索引：只对非null值生效，避免重复键错误
        await collection.create_index(
            [("identifiers.doi", 1)],
            name="doi_unique_index",
            unique=True,
            partialFilterExpression={"identifiers.doi": {"$type": "string"}},
            background=True,
        )
        await collection.create_index(
            [("identifiers.arxiv_id", 1)],
            name="arxiv_unique_index",
            unique=True,
            partialFilterExpression={"identifiers.arxiv_id": {"$type": "string"}},
            background=True,
        )
        
        # 内容指纹唯一索引
        await collection.create_index(
            [("identifiers.fingerprint", 1)],
            name="fingerprint_unique_index",
            unique=True,
            sparse=True,  # 忽略没有该字段的文档
            background=True,
        )

        logger.info("Essential indexes created for task")

    except Exception as e:
        logger.error(f"Failed to create task indexes: {e}")
        # Don't raise - indexes are not critical for task execution
