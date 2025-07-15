from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from literature_parser_backend.db.mongodb import (
    connect_to_mongodb,
    disconnect_from_mongodb,
)


@asynccontextmanager
async def lifespan_setup(
    app: FastAPI,
) -> AsyncGenerator[None, None]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    in the state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    # Initialize MongoDB connection
    try:
        logger.info("Initializing MongoDB connection...")
        await connect_to_mongodb()
        logger.info("MongoDB connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

    app.middleware_stack = None
    app.middleware_stack = app.build_middleware_stack()

    yield

    # Cleanup on shutdown
    try:
        logger.info("Closing MongoDB connection...")
        await disconnect_from_mongodb()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}")
