"""Database layer for literature parser backend."""

from .dao import LiteratureDAO
from .alias_dao import AliasDAO
from .mongodb import (
    close_task_connection,
    connect_to_mongodb,
    create_task_connection,
    create_task_indexes,
    get_database,
    get_task_collection,
    literature_collection,
)

__all__ = [
    "get_database",
    "literature_collection",
    "connect_to_mongodb",
    "LiteratureDAO",
    "AliasDAO",
    "create_task_connection",
    "close_task_connection",
    "get_task_collection",
    "create_task_indexes",
]
