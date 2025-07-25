from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class SelectFilter:
    id: Optional[str] = None
    name: Optional[str] = None
    embedding_model: Optional[str] = None


@dataclass(frozen=True)
class OffsetBasedPagination:
    limit: Optional[int] = None
    offset: Optional[int] = None
    sort_by: Optional[str] = None
    sort_order: Optional[Literal["asc", "desc"]] = None
