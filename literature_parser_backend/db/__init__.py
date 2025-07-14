"""Database layer for literature parser backend."""

from .dao import LiteratureDAO
from .mongodb import connect_to_mongodb, get_database, literature_collection

__all__ = [
    "get_database",
    "literature_collection",
    "connect_to_mongodb",
    "LiteratureDAO",
]
