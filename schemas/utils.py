from typing import Union

from pydantic import BaseModel


class MarkdownResponse(BaseModel):
    markdown: str
    title: Union[str, None] = None


class DeleteRequest(BaseModel):
    ids: Union[list[str], None] = None
    all: bool = False


class DeleteResponse(BaseModel):
    deleted_ids: list[str]
    failed_ids: list[str] = []
    failed_messages: list[str] = []
