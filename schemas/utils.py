from typing import Union

from pydantic import BaseModel


class MarkdownResponse(BaseModel):
    markdown: str
    title: Union[str, None] = None


class DeleteResponse(BaseModel):
    deleted_ids: list[str]
