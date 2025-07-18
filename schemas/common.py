from typing import Annotated, Generic, Literal, Optional, TypeVar, Union

from fastapi import Query
from pydantic import BaseModel
from pydantic.generics import GenericModel


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


T = TypeVar("T")


class PaginatedResponse(GenericModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int


def base_pagination_params(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_order: Annotated[Literal["asc", "desc"], Query()] = "desc",
):
    return {
        "limit": limit,
        "offset": offset,
        "sort_order": sort_order,
    }
