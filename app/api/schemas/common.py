# app/api/schemas/common.py
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base schema enforcing camelCase aliases for JSON serialization and validation."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class MessageResponse(CamelModel):
    message: str


class ReorderRequest(CamelModel):
    ids: list[UUID] = Field(..., min_length=1)
