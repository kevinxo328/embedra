from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.models import CollectionModel
from domains.collection import OffsetBasedPagination, SelectFilter


class CollectionRepositoryCore:
    def __init__(self):
        self.model = CollectionModel

    def _select_expression(self, filter: SelectFilter):
        """
        Returns a SQLAlchemy expression for retrieving collections with optional filters.
        """
        stmt = select(self.model)

        if filter.id:
            stmt = stmt.where(self.model.id == filter.id)

        if filter.name:
            stmt = stmt.where(self.model.name.ilike(f"%{filter.name}%"))

        if filter.embedding_model:
            stmt = stmt.where(
                self.model.embedding_model.ilike(f"%{filter.embedding_model}%")
            )

        return stmt

    def _select_with_pagination_expression(
        self,
        filter: SelectFilter,
        pagination: OffsetBasedPagination,
    ):
        """
        Returns a SQLAlchemy expression for retrieving collections with optional filters and pagination.
        """
        stmt = self._select_expression(filter)

        total_stmt = select(func.count()).select_from(stmt.subquery())

        if pagination.sort_by:
            if pagination.sort_order == "asc":
                stmt = stmt.order_by(getattr(self.model, pagination.sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(self.model, pagination.sort_by).desc())

        if pagination.limit is not None:
            stmt = stmt.limit(pagination.limit)
        if pagination.offset is not None:
            stmt = stmt.offset(pagination.offset)

        return stmt, total_stmt
