from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from database.models import CollectionModel
from domains.collection import OffsetBasedPagination, SelectFilter


class CollectionRepositoryCore:
    def __init__(self):
        self.model = CollectionModel

    def _get_expression(
        self,
        name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """
        Returns a SQLAlchemy expression for retrieving collections with optional filters,

        ### Returns:
        - `stmt`: The main statement to retrieve collections.
        - `total_stmt`: The statement to count total collections before applying limit and offset.
        """

        base_stmt = select(self.model)

        if name:
            base_stmt = base_stmt.where(self.model.name.ilike(f"%{name}%"))

        if embedding_model:
            base_stmt = base_stmt.where(
                self.model.embedding_model.ilike(f"%{embedding_model}%")
            )

        # Count total collections before applying limit and offset
        total_stmt = select(func.count()).select_from(base_stmt.subquery())

        stmt = base_stmt

        if sort_by:
            if sort_order == "asc":
                stmt = stmt.order_by(getattr(self.model, sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(self.model, sort_by).desc())

        if limit is not None:
            stmt = stmt.limit(limit)

        if offset is not None:
            stmt = stmt.offset(offset)

        return stmt, total_stmt

    def _get_by_id_expression(self, id: str, with_files: bool = False):
        """
        Returns a SQLAlchemy expression to retrieve a collection by its ID.
        If `with_files` is True, it will include related files.
        """
        stmt = select(self.model).where(self.model.id == id)

        if with_files:
            stmt = stmt.options(selectinload(self.model.files))

        return stmt

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
