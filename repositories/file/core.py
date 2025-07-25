from typing import Optional

from sqlalchemy import delete, func, select

from database.models import File
from domains.file import OffsetBasedPagination, SelectFilter


class FileRepositoryCore:
    def __init__(self):
        self.model = File

    def _select_expression(self, filter: SelectFilter):
        """
        Returns a SQLAlchemy expression for retrieving files with optional filters.
        """
        stmt = select(self.model)

        if filter.id:
            stmt = stmt.where(self.model.id == filter.id)

        if filter.filename:
            stmt = stmt.where(self.model.filename.ilike(f"%{filter.filename}%"))

        if filter.content_type:
            stmt = stmt.where(self.model.content_type.ilike(f"%{filter.content_type}%"))

        if filter.collection_id:
            stmt = stmt.where(self.model.collection_id == filter.collection_id)

        return stmt

    def _select_with_pagination_expression(
        self, filter: SelectFilter, pagination: OffsetBasedPagination
    ):
        """
        Returns a SQLAlchemy expression for retrieving files with optional filters and pagination.
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

    def _delete_expression(self, collection_id: Optional[str] = None):
        """
        Returns a SQLAlchemy expression to delete files by condition.

        ### Parameters:
        - `collection_id`: Optional collection ID to filter files for deletion.
        """

        stmt = delete(self.model)

        if collection_id:
            stmt = stmt.where(self.model.collection_id == collection_id)

        return stmt
