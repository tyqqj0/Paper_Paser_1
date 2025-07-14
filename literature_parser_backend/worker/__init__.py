"""
Worker package for literature parser backend.

This package contains Celery configuration and task definitions
for asynchronous processing of literature parsing jobs.
"""

from .celery_app import celery_app
from .tasks import process_literature_task

__all__ = [
    "celery_app",
    "process_literature_task",
]
