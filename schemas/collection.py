from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from schemas.common import base_pagination_params
from schemas.embedding import EmbeddingModel


class CollectionUpdate(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionCreate(CollectionUpdate, EmbeddingModel):

    model_config = ConfigDict(from_attributes=True)


class Collection(CollectionCreate):

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class CollectionFilter(BaseModel):
    name: Optional[str] = None
    embedding_model: Optional[str] = None


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
