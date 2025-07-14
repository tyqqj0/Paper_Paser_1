"""
MongoDB connection and collection management.

This module provides MongoDB database connection using Motor
(async MongoDB driver) and manages literature collections.
"""

import logging
from typing import Optional

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from ..settings import Settings

logger = logging.getLogger(__name__)

# Global database client and database instances
_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongodb(
    settings: Optional[Settings] = None,
) -> AsyncIOMotorDatabase:
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
        _database = _client[settings.db_base]

        # Test connection
        await _client.admin.command("ping")
        logger.info(
            f"Successfully connected to MongoDB at {settings.db_host}:{settings.db_port}",
        )

        # Create indexes for better performance
        await create_indexes()

        return _database

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def disconnect_from_mongodb():
    """Disconnect from MongoDB."""
    global _client, _database

    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("Disconnected from MongoDB")


def get_database() -> AsyncIOMotorDatabase:
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


def literature_collection() -> AsyncIOMotorCollection:
    """
    Get the literature collection.

    :return: Literature collection instance
    """
    database = get_database()
    return database.literatures


async def create_indexes():
    """Create necessary indexes for better query performance."""
    try:
        collection = literature_collection()

        # Create indexes for common query patterns
        indexes = [
            # Index on DOI for fast lookups
            ("identifiers.doi", 1),
            # Index on ArXiv ID
            ("identifiers.arxiv_id", 1),
            # Index on fingerprint
            ("identifiers.fingerprint", 1),
            # Compound index for title and author searches
            [("metadata.title", "text"), ("metadata.authors.full_name", "text")],
            # Index on creation time for sorting
            ("created_at", -1),
            # Index on task ID for status queries
            ("task_info.task_id", 1),
        ]

        for index in indexes:
            try:
                if isinstance(index, list):
                    # Text index
                    await collection.create_index(index)
                else:
                    # Regular index
                    await collection.create_index(index)
                logger.debug(f"Created index: {index}")
            except Exception as e:
                logger.warning(f"Failed to create index {index}: {e}")

        logger.info("Successfully created database indexes")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")


async def health_check() -> bool:
    """
    Check if MongoDB connection is healthy.

    :return: True if healthy, False otherwise
    """
    try:
        if _client is None:
            return False

        # Ping the database
        await _client.admin.command("ping")
        return True

    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return False
