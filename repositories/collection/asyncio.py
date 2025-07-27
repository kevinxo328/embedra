from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CollectionModel
from domains.collection import OffsetBasedPagination, SelectFilter

from .core import CollectionRepositoryCore


class CollectionRepositoryAsync(CollectionRepositoryCore):
    def __init__(self, session: AsyncSession):
        super().__init__()
        self.session = session

    async def select_with_pagination(
        self,
        fitter: SelectFilter,
        pagination: OffsetBasedPagination,
    ):
        """Retrieve a list of collections with pagination."""

        stmt, total_stmt = self._select_with_pagination_expression(
            filter=fitter, pagination=pagination
        )

        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar_one()

        result = await self.session.execute(stmt)
        collections = result.scalars().all()

        return collections, total_count

    async def select_one_or_none(self, filter: SelectFilter):
        """Retrieve a collection or return None if not found."""
        stmt = self._select_expression(filter)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def stage_create(self, collection: CollectionModel):
        """Create a new collection."""
        self.session.add(collection)
        return collection

    async def stage_update(self, collection: CollectionModel):
        """
        Update an existing collection.
        #### This method does not commit the transaction.
        """
        await self.session.merge(collection)
        return collection

    async def stage_delete(self, collection: CollectionModel):
        """
        Delete a collection.
        #### This method does not commit the transaction.
        """
        await self.session.delete(collection)
        return True
