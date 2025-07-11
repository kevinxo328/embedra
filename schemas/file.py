from datetime import datetime
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field


class FileBase(BaseModel):
    filename: str
    size: int
    content_type: str


class File(FileBase):
    """
    Represents a file stored in the system.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    collection_id: UUID
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
