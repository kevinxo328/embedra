from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CollectionBase(BaseModel):
    name: str
    description: str | None = None


class Collection(CollectionBase):

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
