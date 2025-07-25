from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class SelectFilter:
    id: Optional[str] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None
    collection_id: Optional[str] = None


@dataclass(frozen=True)
class OffsetBasedPagination:
    limit: Optional[int] = None
    offset: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: Optional[Literal["asc", "desc"]] = None
