#!/usr/bin/env python3
"""
Celery worker startup script.

This script starts a Celery worker with proper configuration
for literature processing tasks.
"""

import logging
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from literature_parser_backend.worker.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main() -> None:
    """Entry point for starting the Celery worker."""
    # This is a simple wrapper for the Celery CLI.
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--concurrency=1",  # Single process for literature processing
            "--queues=literature",  # Only process literature queue
            "--hostname=literature-worker@%h",
        ],
    )


if __name__ == "__main__":
    main()
