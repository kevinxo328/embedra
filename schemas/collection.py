from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from schemas.common import base_pagination_params
from settings import DEFAULT_EMBEDDING_MODEL


class CollectionUpdate(BaseModel):
    name: str
    description: str | None = None


class CollectionCreate(CollectionUpdate):
    embedding_model: str = DEFAULT_EMBEDDING_MODEL


class Collection(CollectionCreate):

    model_config = ConfigDict(from_attributes=True)

    id: Union[UUID, str]
    created_at: datetime
    updated_at: datetime


class CollectionFilter(BaseModel):
    name: Union[str, None] = None
    embedding_model: Union[str, None] = None


class CollectionPaginationParams:
    def __init__(
        self,
        pagination: dict = Depends(base_pagination_params),
        sort_by: Annotated[
            Optional[Literal["created_at", "name", "embedding_model"]],
            Query(description="Column to sort by"),
        ] = "created_at",
    ):
        self.limit = pagination.get("limit", 20)
        self.offset = pagination.get("offset", 0)
        self.sort_order = pagination.get("sort_order", "desc")
        self.sort_by = sort_by or "created_at"
