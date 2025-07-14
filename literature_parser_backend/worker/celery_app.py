"""
Celery application configuration.

This module sets up the Celery instance with Redis as broker
and result backend, configured from the application settings.
"""

import logging

from celery import Celery

from ..settings import Settings

logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Create Celery instance
celery_app = Celery(
    "literature_parser_worker",
    broker=settings.celery_broker_url_computed,
    backend=settings.celery_result_backend_computed,
)

# Configure Celery
celery_app.conf.update(
    # Serialization settings
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,
    # Timezone settings
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,
    # Task execution settings
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    # Worker settings
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,
    # Task routing
    task_routes={
        "literature_parser_worker.tasks.*": {"queue": "literature"},
    },
    # Include task modules
    include=[
        "literature_parser_backend.worker.tasks",
    ],
)

# Optional: Configure logging for Celery
celery_app.conf.update(
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

logger.info(f"Celery app configured with broker: {settings.celery_broker_url_computed}")
logger.info(
    f"Celery app configured with backend: {settings.celery_result_backend_computed}",
)


# Health check function
def health_check() -> bool:
    """
    Check if Celery broker (Redis) is accessible.

    :return: True if healthy, False otherwise.
    """
    try:
        # Test broker connection
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        return stats is not None
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return False
