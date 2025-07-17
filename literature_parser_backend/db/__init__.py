"""Database layer for literature parser backend."""

from .dao import LiteratureDAO
from .mongodb import (
    connect_to_mongodb,
    get_database,
    literature_collection,
    create_task_connection,
    close_task_connection,
    get_task_collection,
    create_task_indexes,
)

__all__ = [
    "get_database",
    "literature_collection",
    "connect_to_mongodb",
    "LiteratureDAO",
    "create_task_connection",
    "close_task_connection",
    "get_task_collection",
    "create_task_indexes",
]
