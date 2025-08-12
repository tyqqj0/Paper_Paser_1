"""
Base DAO class for Neo4j operations.

This module provides a common base class for all Neo4j Data Access Objects,
containing shared functionality like connection management, data serialization,
and common query patterns.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from neo4j import AsyncDriver, AsyncSession
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseNeo4jDAO:
    """
    Base class for all Neo4j Data Access Objects.
    
    Provides common functionality:
    - Neo4j driver and session management
    - Data serialization for Neo4j storage
    - Connection initialization patterns
    - Transaction management helpers
    """
    
    def __init__(
        self,
        database: Optional[AsyncDriver] = None,
        collection: Optional[AsyncDriver] = None,
    ) -> None:
        """
        Initialize DAO with Neo4j driver.
        
        :param database: Neo4j driver instance (optional)
        :param collection: Neo4j driver instance (optional, same as database for compatibility)
        """
        if collection is not None:
            self.driver = collection
        elif database is not None:
            self.driver = database
        else:
            from .neo4j import get_database
            self.driver = get_database()
    
    @classmethod
    def create_from_task_connection(cls, database: AsyncDriver) -> "BaseNeo4jDAO":
        """Create DAO instance using task-level Neo4j driver."""
        return cls(database=database)
    
    @classmethod
    def create_from_global_connection(cls) -> "BaseNeo4jDAO":
        """Create DAO instance using global Neo4j connection."""
        return cls()
    
    def _get_session(self, **kwargs) -> AsyncSession:
        """Get Neo4j session with optional configuration."""
        return self.driver.session(**kwargs)
    
    def _clean_for_neo4j(self, data: Any) -> str:
        """
        Clean data for Neo4j storage - convert complex objects to JSON strings.
        
        Neo4j only supports primitive types as property values.
        We serialize complex data as JSON strings for storage.
        
        :param data: Data to clean and serialize
        :return: JSON string representation
        """
        def clean_recursive(obj):
            """Recursively clean object by removing None and converting to serializable types."""
            if obj is None:
                return None
            elif isinstance(obj, (str, int, float, bool)):
                return obj
            elif isinstance(obj, list):
                return [clean_recursive(item) for item in obj if clean_recursive(item) is not None]
            elif isinstance(obj, dict):
                cleaned = {}
                for key, value in obj.items():
                    cleaned_value = clean_recursive(value)
                    if cleaned_value is not None:
                        cleaned[key] = cleaned_value
                return cleaned
            elif hasattr(obj, 'value'):  # Handle Enum objects
                return obj.value
            elif hasattr(obj, 'model_dump'):  # Handle Pydantic models
                return clean_recursive(obj.model_dump())
            elif hasattr(obj, 'isoformat'):  # Handle datetime objects
                return obj.isoformat()
            else:
                # Convert unknown types to string
                return str(obj)

        try:
            cleaned_data = clean_recursive(data)
            return json.dumps(cleaned_data, ensure_ascii=False) if cleaned_data else ""
        except Exception as e:
            logger.error(f"Failed to clean data for Neo4j: {e}")
            return ""
    
    def _parse_json_field(self, json_str: Optional[str]) -> Dict[str, Any]:
        """
        Parse JSON string field back to Python object.
        
        :param json_str: JSON string to parse
        :return: Parsed dictionary or empty dict if parsing fails
        """
        if not json_str:
            return {}
        
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse JSON field: {e}")
            return {}
    
    async def _execute_cypher(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        single_result: bool = False
    ) -> Any:
        """
        Execute a Cypher query with error handling.
        
        :param query: Cypher query string
        :param parameters: Query parameters
        :param single_result: Whether to return single result or all results
        :return: Query results
        """
        try:
            async with self._get_session() as session:
                result = await session.run(query, **(parameters or {}))
                
                if single_result:
                    return await result.single()
                else:
                    return await result.data()
                    
        except Exception as e:
            logger.error(f"Cypher query failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    async def _transaction_execute(
        self,
        queries_and_params: list,
        rollback_on_error: bool = True
    ) -> list:
        """
        Execute multiple queries in a single transaction.
        
        :param queries_and_params: List of (query, parameters) tuples
        :param rollback_on_error: Whether to rollback on error
        :return: List of results
        """
        results = []
        
        async with self._get_session() as session:
            tx = await session.begin_transaction()
            
            try:
                for query, params in queries_and_params:
                    result = await tx.run(query, **(params or {}))
                    results.append(await result.data())
                
                await tx.commit()
                logger.debug(f"Transaction committed successfully with {len(queries_and_params)} queries")
                
            except Exception as e:
                if rollback_on_error:
                    await tx.rollback()
                    logger.error(f"Transaction failed, rolled back: {e}")
                else:
                    logger.error(f"Transaction failed: {e}")
                raise
            finally:
                await tx.close()
                
        return results
