from typing import Optional

from sqlalchemy.orm import Session

from database.models import Collection

from .core import CollectionRepositoryCore


class CollectionRepositorySync(CollectionRepositoryCore):
    def __init__(self, session: Session):
        super().__init__()
        self.session = session

    def get(
        self,
        name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """Retrieve a list of collections with pagination."""

        stmt, total_stmt = self._get_expression(
            name=name,
            embedding_model=embedding_model,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        total_result = self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        result = self.session.execute(stmt)
        collections = result.scalars().all()

        return collections, total_count

    def get_by_id(self, id: str, with_files: bool = False):
        """Retrieve a collection by its ID."""
        stmt = self._get_by_id_expression(id, with_files=with_files)

        result = self.session.execute(stmt)
        return result.scalar_one()

    def get_by_id_or_none(self, id: str, with_files: bool = False):
        """Retrieve a collection by its ID or return None if not found."""
        stmt = self._get_by_id_expression(id, with_files=with_files)

        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def stage_create(self, collection: Collection):
        """Create a new collection."""
        self.session.add(collection)
        return collection

    def stage_update(self, collection: Collection):
        """
        Update an existing collection.
        #### This method does not commit the transaction.
        """
        self.session.merge(collection)
        return collection

    def stage_delete(self, collection: Collection):
        """
        Delete a collection.
        #### This method does not commit the transaction.
        """
        self.session.delete(collection)
        return True
