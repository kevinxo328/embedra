from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from settings import DEFAULT_EMBEDDING_MODEL


class CollectionUpdate(BaseModel):
    name: str
    description: str | None = None


class CollectionCreate(CollectionUpdate):
    embedding_model: str = DEFAULT_EMBEDDING_MODEL


class Collection(CollectionCreate):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
