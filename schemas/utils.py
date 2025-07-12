from typing import Union

from pydantic import BaseModel


class MarkdownResponse(BaseModel):
    markdown: str
    title: Union[str, None] = None
