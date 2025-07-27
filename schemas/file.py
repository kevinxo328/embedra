from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Optional

from fastapi import Depends, Query, UploadFile
from pydantic import BaseModel, ConfigDict

from schemas.common import base_pagination_params


class FileBase(BaseModel):
    filename: str
    size: int
    content_type: str


class FileStatus(Enum):
    """
    Represents the various states a file can be in during processing.

    The states include:
    - UPLOADED: The file has been uploaded successfully and waiting for chunking.
    - CHUNKED: The file has been successfully chunked.
    - CHUNK_FAILED: The file chunking failed.
    - EMBEDDING: The file is currently being embedded.
    - SUCCESS: The file processing was successful.
    - FAILED: Some or all chunks of the file failed to embed.
    """

    UPLOADED = "uploaded"
    CHUNKED = "chunked"
    CHUNK_FAILED = "chunk_failed"
    EMBEDDING = "embedding"
    SUCCESS = "success"
    FAILED = "failed"


class File(FileBase):
    """
    Represents a file stored in the system.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    collection_id: str
    path: str
    created_at: datetime
    size: int
    status: FileStatus


class ValidatedUploadFile(UploadFile):
    """
    A validated version of UploadFile.
    This class is used to ensure that the uploaded file has been validated and is safe to use.
    """

    filename: str
    size: int
    content_type: str


class FileFilter(BaseModel):
    filename: Optional[str] = None
    content_type: Optional[str] = None


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
