"""Database layer for literature parser backend."""

from .dao import LiteratureDAO
from .alias_dao import AliasDAO
from .relationship_dao import RelationshipDAO
from .neo4j import (
    close_task_connection,
    connect_to_neo4j,
    connect_to_mongodb,  # Compatibility name for Neo4j connection  
    create_task_connection,
    create_task_indexes,
    get_database,
    get_neo4j_session,
    get_task_collection,
    literature_collection,  # Compatibility name for get_neo4j_session
)

__all__ = [
    "get_database",
    "get_neo4j_session",
    "literature_collection",  # Compatibility alias
    "connect_to_neo4j",
    "connect_to_mongodb",  # Compatibility alias - actually connects to Neo4j
    "LiteratureDAO",
    "AliasDAO",
    "RelationshipDAO",
    "create_task_connection",
    "close_task_connection",
    "get_task_collection",
    "create_task_indexes",
]
