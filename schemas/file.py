from datetime import datetime
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from fastapi import Depends, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import base_pagination_params


class FileBase(BaseModel):
    filename: str
    size: int
    content_type: str


class File(FileBase):
    """
    Represents a file stored in the system.
    """

    model_config = ConfigDict(from_attributes=True)

    id: Union[UUID, str]
    collection_id: Union[UUID, str]
    path: str
    created_at: datetime

    # TODO: align with database model
    size: int = Field(..., alias="filesize")


class ValidatedUploadFile(UploadFile):
    """
    A validated version of UploadFile.
    This class is used to ensure that the uploaded file has been validated and is safe to use.
    """

    filename: str
    size: int
    content_type: str


class FileFilter(BaseModel):
    filename: Union[str, None] = None
    content_type: Union[str, None] = None


class FilePaginationParams:
    def __init__(
        self,
        pagination: dict = Depends(base_pagination_params),
        sort_by: Annotated[
            Optional[Literal["created_at", "name", "content_type"]],
            Query(description="Column to sort by"),
        ] = "created_at",
    ):
        self.limit = pagination.get("limit", 20)
        self.offset = pagination.get("offset", 0)
        self.sort_order = pagination.get("sort_order", "desc")
        self.sort_by = sort_by or "created_at"
