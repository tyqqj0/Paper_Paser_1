"""
Common model components and utilities.
"""

from typing import Annotated, Any

from bson import ObjectId
from pydantic import (
    BeforeValidator,
    Field,
    GetJsonSchemaHandler,
    PlainSerializer,
    WithJsonSchema,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """
    Custom ObjectId type for Pydantic v2.

    This class allows seamless integration between MongoDB's ObjectId
    and Pydantic models, handling both serialization and validation.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetJsonSchemaHandler,
    ) -> core_schema.CoreSchema:
        """Define the core schema for PyObjectId validation."""
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(cls.validate),
                        ],
                    ),
                ],
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
            ),
        )

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        """Validate and convert input to ObjectId."""
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str):
            try:
                return ObjectId(value)
            except Exception as e:
                raise ValueError(f"Invalid ObjectId: {value}") from e
        raise ValueError(f"Invalid type for ObjectId: {type(value)}")

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """Define JSON schema for API documentation."""
        return {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{24}$",
            "description": "MongoDB ObjectId as a 24-character hex string",
            "example": "507f1f77bcf86cd799439011",
        }
