#!/usr/bin/env python3
"""
Convenient script to start Celery worker for literature processing.

Usage:
    python start_worker.py

This script will start a Celery worker configured for literature processing.
Make sure Redis is running before starting the worker.
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    """Start the Celery worker."""
    # Change to the project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    print("🚀 Starting Literature Parser Celery Worker...")
    print("📁 Working directory:", project_dir)
    print("🔄 Make sure Redis is running on localhost:6379")
    print("-" * 50)

    # Start celery worker
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "literature_parser_backend.worker.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=1",
        "--queues=literature",
        "--hostname=literature-worker@%h",
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n⏹️  Worker stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Worker failed with exit code {e.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
