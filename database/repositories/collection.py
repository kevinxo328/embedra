from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.collection import Collection


class CollectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self,
        name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """Retrieve a list of collections with pagination."""

        base_stmt = select(Collection)

        if name:
            base_stmt = base_stmt.where(Collection.name.ilike(f"%{name}%"))

        if embedding_model:
            base_stmt = base_stmt.where(Collection.embedding_model == embedding_model)

        # Count total collections before applying limit and offset
        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        # Apply limit and offset for pagination
        stmt = base_stmt

        if sort_by:
            if sort_order == "asc":
                stmt = stmt.order_by(getattr(Collection, sort_by).asc())
            else:
                stmt = stmt.order_by(getattr(Collection, sort_by).desc())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        collections = result.scalars().all()

        return collections, total_count

    async def get_by_id(self, id: str, with_files: bool = False):
        """Retrieve a collection by its ID."""
        stmt = select(Collection).where(Collection.id == id)

        if with_files:
            stmt = stmt.options(selectinload(Collection.files))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stage_create(self, collection: Collection):
        """Create a new collection."""
        self.session.add(collection)
        return collection

    async def stage_update(self, collection: Collection):
        """
        Update an existing collection.
        This method does not commit the transaction.
        """
        await self.session.merge(collection)
        return collection

    async def stage_delete(self, collection: Collection):
        """
        Delete a collection.
        This method does not commit the transaction.
        """
        await self.session.delete(collection)
        return True
