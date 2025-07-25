from typing import Optional

from sqlalchemy import delete, func, select

from ...models.file import File


class FileRepositoryCore:
    def __init__(self):
        self.model = File

    def _get_expression(
        self,
        collection_id: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """
        Returns a SQLAlchemy expression for retrieving files with optional filters.

        ### Returns:
        - `stmt`: The main statement to retrieve files.
        - `total_stmt`: The statement to count total files before applying limit and offset.
        """

        base_stmt = select(self.model).where(self.model.collection_id == collection_id)

        if filename:
            base_stmt = base_stmt.where(self.model.filename.ilike(f"%{filename}%"))

        if content_type:
            base_stmt = base_stmt.where(
                self.model.content_type.ilike(f"%{content_type}%")
            )

        # Count total files before applying limit and offset
        total_stmt = select(func.count()).select_from(base_stmt.subquery())

        # Apply limit and offset for pagination
        stmt = base_stmt

        if sort_by:
            if sort_order == "asc":
                stmt = stmt.order_by(getattr(self.model, sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(self.model, sort_by).desc())

        stmt = stmt.limit(limit).offset(offset)

        return stmt, total_stmt

    def _get_by_id_expression(self, id: str):
        """Retrieve a file by its ID."""
        return select(self.model).where(self.model.id == id)

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
