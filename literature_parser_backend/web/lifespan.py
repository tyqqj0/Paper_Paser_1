"""Application lifespan management for Neo4j database connection."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from literature_parser_backend.db.neo4j import (
    connect_to_neo4j,
    disconnect_from_neo4j,
)


@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None, None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function initializes the Neo4j database connection.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    # Initialize Neo4j connection
    try:
        logger.info("Initializing Neo4j connection...")
        await connect_to_neo4j()
        logger.info("Neo4j connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise

    yield

    # Cleanup on shutdown
    try:
        logger.info("Closing Neo4j connection...")
        await disconnect_from_neo4j()
        logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error closing Neo4j connection: {e}")