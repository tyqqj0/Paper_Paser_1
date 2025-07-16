"""Common model components and utilities."""

from typing import Any, ClassVar, Dict

from bson import ObjectId
from pydantic import (
    GetJsonSchemaHandler,
    Field,
    GetCoreSchemaHandler,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema, CoreSchema


class PyObjectId(ObjectId):
    """Custom Pydantic type for MongoDB's ObjectId."""

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> Dict[str, Any]:
        """Return JSON schema for ObjectId."""
        json_schema = handler(core_schema)
        json_schema.update(
            type="string",
            examples=["507f1f77bcf86cd799439011"],
        )
        return json_schema

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Return Pydantic core schema."""
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(ObjectId),
                    core_schema.chain_schema(
                        [
                            core_schema.str_schema(),
                            core_schema.no_info_plain_validator_function(
                                cls.validate_object_id,
                            ),
                        ],
                    ),
                ],
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
            ),
        )

    @staticmethod
    def validate_object_id(v: str) -> ObjectId:
        """Validate string as ObjectId."""
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def MongoId(
    title: str = "Database ID",
    description: str = "MongoDB document _id",
    example: str = "507f1f77bcf86cd799439011",
) -> Any:
    """Create a Pydantic Field for a MongoDB ID."""
    return Field(
        default=None,
        alias="_id",
        title=title,
        description=description,
        json_schema_extra={"example": example},
    )
