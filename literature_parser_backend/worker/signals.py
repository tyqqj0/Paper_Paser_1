"""
Celery worker signal handlers.

This module contains Celery signal handlers to initialize
and clean up resources when workers start and terminate.
"""

import asyncio
import logging
from celery.signals import (
    worker_init, worker_process_init, worker_shutdown, worker_process_shutdown
)

from literature_parser_backend.db.neo4j import (
    connect_to_mongodb,  # Actually connects to Neo4j (compatibility name)
    disconnect_from_mongodb,  # Actually disconnects from Neo4j
)
from literature_parser_backend.settings import Settings

logger = logging.getLogger(__name__)

@worker_process_init.connect
def init_worker_process(sender=None, **kwargs):
    """
    Initialize resources when a worker process starts.
    
    This runs in each worker process and is the right place to initialize
    per-process resources like database connections.
    """
    logger.info("Initializing worker process resources...")
    
    # Initialize Neo4j connection using asyncio
    loop = asyncio.get_event_loop()
    try:
        logger.info("Initializing Neo4j connection for worker process...")
        # Run the async connect function in the event loop
        loop.run_until_complete(connect_to_mongodb())
        logger.info("Neo4j connection established for worker process")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j in worker process: {e}")
        # Continue execution even if database connection fails
        # Tasks will fail individually with proper error handling
    
    logger.info("Worker process initialization completed")

@worker_process_shutdown.connect
def cleanup_worker_process(sender=None, **kwargs):
    """
    Clean up resources when a worker process shuts down.
    """
    logger.info("Cleaning up worker process resources...")
    
    # Close Neo4j connection using asyncio
    loop = asyncio.get_event_loop()
    try:
        logger.info("Closing Neo4j connection for worker process...")
        # Run the async disconnect function in the event loop
        loop.run_until_complete(disconnect_from_mongodb())
        logger.info("Neo4j connection closed for worker process")
    except Exception as e:
        logger.error(f"Error closing Neo4j connection in worker process: {e}")
    
    logger.info("Worker process cleanup completed")